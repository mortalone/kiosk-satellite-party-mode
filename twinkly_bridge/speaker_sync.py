"""Automatic UPnP/Sonos playback buffer synchronization without microphones."""
import asyncio
import ipaddress
import json
import logging
import re
import socket
import threading
import time
import urllib.request
from pathlib import Path
from urllib.parse import urlsplit
import xml.etree.ElementTree as ET

LOG = logging.getLogger("speaker_sync")

SOAP_ENV = (
    '<?xml version="1.0" encoding="utf-8"?>'
    '<s:Envelope xmlns:s="http://schemas.xmlsoap.org/soap/envelope/" '
    's:encodingStyle="http://schemas.xmlsoap.org/soap/encoding/">'
    "<s:Body>{body}</s:Body></s:Envelope>"
)
ZONE_GROUP_BODY = SOAP_ENV.format(
    body='<u:GetZoneGroupState xmlns:u="urn:schemas-upnp-org:service:ZoneGroupTopology:1"></u:GetZoneGroupState>'
)
TRANSPORT_BODY = SOAP_ENV.format(
    body='<u:GetTransportInfo xmlns:u="urn:schemas-upnp-org:service:AVTransport:1"><InstanceID>0</InstanceID></u:GetTransportInfo>'
)
POSITION_BODY = SOAP_ENV.format(
    body='<u:GetPositionInfo xmlns:u="urn:schemas-upnp-org:service:AVTransport:1"><InstanceID>0</InstanceID></u:GetPositionInfo>'
)


def parse_rel_time(text):
    if not text or not isinstance(text, str):
        return None
    parts = text.strip().split(":")
    if len(parts) != 3:
        return None
    try:
        hours, minutes, seconds = int(parts[0]), int(parts[1]), float(parts[2])
    except ValueError:
        return None
    if hours < 0 or not 0 <= minutes < 60 or not 0 <= seconds < 60:
        return None
    return hours * 3600 + minutes * 60 + seconds


def extract_tag(xml_text, tag):
    match = re.search(rf"<(?:\w+:)?{re.escape(tag)}>([^<]*)</(?:\w+:)?{re.escape(tag)}>", xml_text or "")
    if not match:
        return ""
    value = match.group(1)
    return (
        value.replace("&lt;", "<")
        .replace("&gt;", ">")
        .replace("&quot;", '"')
        .replace("&apos;", "'")
        .replace("&amp;", "&")
    )


def parse_zone_groups(soap_xml):
    inner = extract_tag(soap_xml, "ZoneGroupState")
    if not inner:
        return []
    try:
        root = ET.fromstring(inner)
    except ET.ParseError:
        return []
    speakers = []
    seen = set()
    for group in root.iter("ZoneGroup"):
        coordinator_uuid = group.attrib.get("Coordinator", "").strip()
        members = list(group.iter("ZoneGroupMember"))
        coord_member = None
        visible_name = ""
        for member in members:
            if member.attrib.get("Invisible") != "1" and member.attrib.get("ZoneName"):
                visible_name = member.attrib.get("ZoneName", "").strip()
            if member.attrib.get("UUID", "").strip() == coordinator_uuid:
                coord_member = member
        if coord_member is None and members:
            coord_member = members[0]
        if coord_member is None:
            continue
        uuid = coord_member.attrib.get("UUID", "").strip()
        location = coord_member.attrib.get("Location", "").strip()
        name = visible_name or coord_member.attrib.get("ZoneName", "").strip() or uuid
        parsed = urlsplit(location)
        host = parsed.hostname or ""
        port = parsed.port or 1400
        if not uuid or not host or uuid in seen:
            continue
        seen.add(uuid)
        speakers.append({"uuid": uuid, "name": name, "ip": host, "port": port})
    speakers.sort(key=lambda item: item["name"].lower())
    return speakers


def select_speaker(speakers, selection, group_name="", transport_map=None):
    mode = (selection or "auto").strip()
    if mode.lower() in {"off", "none", "false", "disabled"}:
        return None
    transport_map = transport_map or {}
    if mode.lower() not in {"", "auto"}:
        lower = mode.lower()
        host_only = mode.split(":")[0].strip()
        for speaker in speakers:
            if (
                speaker["uuid"].lower() == lower
                or speaker["ip"] == mode
                or speaker["ip"] == host_only
                or f"{speaker['ip']}:{speaker.get('port', 1400)}" == mode
                or speaker["name"].lower() == lower
            ):
                return speaker
        for speaker in speakers:
            if lower in speaker["name"].lower() or speaker["name"].lower() in lower:
                return speaker
        return None

    # Auto mode: 1) Active coordinator playing Music Assistant UGP stream
    for state_filter in ({"PLAYING", "TRANSITIONING"}, {"PLAYING", "TRANSITIONING", "PAUSED_PLAYBACK", "STOPPED"}):
        for speaker in speakers:
            info = transport_map.get(speaker["uuid"], {})
            uri = (info.get("uri") or "").lower()
            state = info.get("state") or ""
            if state in state_filter and ("/ugp/" in uri or "flowmode" in uri or "x-rincon-mp3radio://" in uri):
                if state in {"PLAYING", "TRANSITIONING"}:
                    return speaker
                if group_name and (
                    group_name.lower() in speaker["name"].lower() or speaker["name"].lower() in group_name.lower()
                ):
                    return speaker

    # 2) Match Sendspin group_name against Sonos ZoneName
    if group_name:
        g_low = group_name.strip().lower()
        for speaker in speakers:
            s_low = speaker["name"].strip().lower()
            if s_low == g_low or s_low.startswith(g_low) or g_low.startswith(s_low):
                return speaker

    # 3) Any speaker with a UGP URI loaded, or the sole playing speaker
    for speaker in speakers:
        uri = (transport_map.get(speaker["uuid"], {}).get("uri") or "").lower()
        if "/ugp/" in uri or "flowmode" in uri:
            return speaker
    playing = [s for s in speakers if transport_map.get(s["uuid"], {}).get("state") in {"PLAYING", "TRANSITIONING"}]
    if len(playing) == 1:
        return playing[0]
    return speakers[0] if len(speakers) == 1 else None


def soap_post_sync(ip, port, path, action, body, timeout=0.6):
    url = f"http://{ip}:{port}{path}"
    req = urllib.request.Request(
        url,
        data=body.encode("utf-8"),
        headers={
            "Content-Type": 'text/xml; charset="utf-8"',
            "SOAPAction": f'"{action}"',
        },
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        if resp.status != 200:
            return ""
        return resp.read().decode("utf-8", errors="replace")


class SpeakerSync:
    """Discover local UPnP/Sonos speakers and lock onto their real HTTP stream buffer delay."""

    def __init__(self, options, directory=Path("/data"), on_delay=None, diagnostic=None):
        self.directory = Path(directory)
        self.cache_path = self.directory / "speaker_sync.json"
        self.on_delay = on_delay
        self.diagnostic = diagnostic
        self.selection = str(options.get("sync_speaker", "auto") or "auto").strip() or "auto"
        self.sendspin_url = str(options.get("sendspin_url", "") or "").strip()
        self.device_ip = str(options.get("device_ip", "") or "").strip()
        self.lock = threading.Lock()
        self.wake = threading.Event()
        self.stream_start_at = None
        self.group_name = ""
        self.speakers = []
        self.cached_ip = ""
        self.persisted_delay_ms = 0
        self._load_cache()
        enabled = self.selection.lower() not in {"off", "none", "false", "disabled"}
        initial_delay = self.persisted_delay_ms if enabled else 0
        self.info = {
            "selection": self.selection,
            "state": "waiting" if enabled else "disabled",
            "speaker_name": "",
            "speaker_uuid": "",
            "speaker_ip": "",
            "transport_state": "",
            "rel_time": "",
            "auto_delay_ms": initial_delay,
            "locked": False,
            "speakers": [],
        }

    def _load_cache(self):
        try:
            data = json.loads(self.cache_path.read_text())
            if isinstance(data, dict):
                self.cached_ip = str(data.get("speaker_ip", "") or "")
                delay = int(data.get("auto_delay_ms", 0) or 0)
                if 0 <= delay <= 8000:
                    self.persisted_delay_ms = delay
                saved_sel = str(data.get("selection", "") or "").strip()
                if saved_sel and self.selection == "auto":
                    self.selection = saved_sel
        except (OSError, ValueError, TypeError):
            pass

    def _save_cache(self, speaker_ip="", auto_delay_ms=None):
        try:
            self.directory.mkdir(parents=True, exist_ok=True)
            payload = {
                "selection": self.selection,
                "speaker_ip": speaker_ip or self.cached_ip,
                "auto_delay_ms": self.persisted_delay_ms if auto_delay_ms is None else int(auto_delay_ms),
            }
            self.cache_path.write_text(json.dumps(payload))
        except OSError:
            pass

    def status(self):
        with self.lock:
            result = dict(self.info)
            result["speakers"] = [dict(s) for s in self.speakers]
            return result

    def set_selection(self, selection):
        value = str(selection or "auto").strip() or "auto"
        enabled = value.lower() not in {"off", "none", "false", "disabled"}
        with self.lock:
            self.selection = value
            self.info["selection"] = value
            self.info["locked"] = False
            if not enabled:
                self.info.update(
                    state="disabled",
                    speaker_name="",
                    speaker_uuid="",
                    speaker_ip="",
                    transport_state="",
                    rel_time="",
                    auto_delay_ms=0,
                )
        self._save_cache()
        if not enabled and self.on_delay is not None:
            self.on_delay(0)
        elif enabled and self.persisted_delay_ms and self.on_delay is not None:
            with self.lock:
                self.info["auto_delay_ms"] = self.persisted_delay_ms
                self.info["state"] = "measuring"
            self.on_delay(self.persisted_delay_ms)
        self.wake.set()

    def set_group_name(self, group_name):
        with self.lock:
            changed = (group_name or "") != self.group_name
            self.group_name = group_name or ""
        if changed:
            self.wake.set()

    def on_stream_start(self, unadjusted_due):
        with self.lock:
            self.stream_start_at = unadjusted_due
            self.info["locked"] = False
            enabled = self.selection.lower() not in {"off", "none", "false", "disabled"}
            if enabled and self.persisted_delay_ms > 0 and self.info["auto_delay_ms"] == 0:
                self.info["auto_delay_ms"] = self.persisted_delay_ms
                delay_to_apply = self.persisted_delay_ms
            else:
                delay_to_apply = None
        if delay_to_apply is not None and self.on_delay is not None:
            self.on_delay(delay_to_apply)
        self.wake.set()

    def on_stream_clear(self):
        with self.lock:
            self.stream_start_at = None
            self.info["locked"] = False

    def candidate_endpoints(self):
        endpoints = []
        with self.lock:
            selection = self.selection
            cached = self.cached_ip
        for raw in (selection, cached):
            if not raw:
                continue
            parts = raw.strip().split(":")
            host = parts[0].strip()
            port = int(parts[1]) if len(parts) == 2 and parts[1].isdigit() else 1400
            try:
                addr = ipaddress.ip_address(host)
                if addr.version == 4 and (not addr.is_loopback or len(parts) == 2):
                    endpoints.append((str(addr), port))
            except ValueError:
                pass
        return endpoints

    def candidate_subnets(self):
        subnets = []
        hosts = []
        if self.sendspin_url:
            parsed = urlsplit(self.sendspin_url)
            if parsed.hostname:
                hosts.append(parsed.hostname)
        if self.device_ip:
            hosts.append(self.device_ip)
        for ip, _ in self.candidate_endpoints():
            hosts.append(ip)
        for host in hosts:
            try:
                addr = ipaddress.ip_address(host)
                if addr.version == 4 and addr.is_private and not addr.is_loopback:
                    prefix = ".".join(str(addr).split(".")[:3])
                    if prefix not in subnets:
                        subnets.append(prefix)
            except ValueError:
                pass
        return subnets

    @staticmethod
    async def soap_call(ip, port, path, action, body, timeout=0.6):
        return await asyncio.to_thread(soap_post_sync, ip, port, path, action, body, timeout)

    async def query_zone_groups(self, ip, port=1400):
        try:
            xml_text = await self.soap_call(
                ip,
                port,
                "/ZoneGroupTopology/Control",
                "urn:schemas-upnp-org:service:ZoneGroupTopology:1#GetZoneGroupState",
                ZONE_GROUP_BODY,
                timeout=0.8,
            )
            return parse_zone_groups(xml_text)
        except Exception:
            return []

    async def query_transport_and_position(self, ip, port=1400):
        t0 = time.monotonic()
        transport_xml, position_xml = await asyncio.gather(
            self.soap_call(
                ip,
                port,
                "/MediaRenderer/AVTransport/Control",
                "urn:schemas-upnp-org:service:AVTransport:1#GetTransportInfo",
                TRANSPORT_BODY,
                timeout=0.45,
            ),
            self.soap_call(
                ip,
                port,
                "/MediaRenderer/AVTransport/Control",
                "urn:schemas-upnp-org:service:AVTransport:1#GetPositionInfo",
                POSITION_BODY,
                timeout=0.45,
            ),
        )
        t1 = time.monotonic()
        state = extract_tag(transport_xml, "CurrentTransportState")
        rel_str = extract_tag(position_xml, "RelTime")
        uri = extract_tag(position_xml, "TrackURI")
        return {
            "state": state,
            "rel_str": rel_str,
            "rel_s": parse_rel_time(rel_str),
            "uri": uri,
            "sampled_at": (t0 + t1) / 2,
        }

    async def discover_speakers(self):
        known = list(self.candidate_endpoints())
        with self.lock:
            for s in self.speakers:
                pair = (s["ip"], s.get("port", 1400))
                if pair not in known:
                    known.append(pair)
        for ip, port in known:
            found = await self.query_zone_groups(ip, port)
            if found:
                self.cached_ip = f"{ip}:{port}" if port != 1400 else ip
                with self.lock:
                    self.speakers = found
                    self.info["speakers"] = [dict(s) for s in found]
                return found

        for prefix in self.candidate_subnets():
            hosts = [f"{prefix}.{i}" for i in range(1, 255)]
            for idx in range(0, len(hosts), 32):
                batch = hosts[idx : idx + 32]
                probes = [self._probe_port(ip, 1400, 0.18) for ip in batch]
                results = await asyncio.gather(*probes)
                for ip, open_ok in zip(batch, results):
                    if not open_ok:
                        continue
                    found = await self.query_zone_groups(ip, 1400)
                    if found:
                        self.cached_ip = ip
                        self._save_cache(speaker_ip=ip)
                        with self.lock:
                            self.speakers = found
                            self.info["speakers"] = [dict(s) for s in found]
                        return found
        return []

    @staticmethod
    async def _probe_port(ip, port, timeout):
        try:
            _, writer = await asyncio.wait_for(asyncio.open_connection(ip, port), timeout=timeout)
            writer.close()
            try:
                await writer.wait_closed()
            except Exception:
                pass
            return True
        except Exception:
            return False

    async def resolve_target_speaker(self):
        with self.lock:
            selection = self.selection
            group_name = self.group_name
            speakers = list(self.speakers)
        if selection.lower() in {"off", "none", "false", "disabled"}:
            return None, {}
        if not speakers:
            speakers = await self.discover_speakers()
        if not speakers:
            endpoints = self.candidate_endpoints()
            if endpoints:
                ip, port = endpoints[0]
                direct = {"uuid": ip, "name": ip, "ip": ip, "port": port}
                return direct, {}
            return None, {}

        transport_map = {}
        if selection.lower() in {"", "auto"} or len(speakers) > 1:
            infos = await asyncio.gather(
                *(self.query_transport_and_position(s["ip"], s["port"]) for s in speakers),
                return_exceptions=True,
            )
            for speaker, info in zip(speakers, infos):
                if isinstance(info, dict):
                    transport_map[speaker["uuid"]] = info
        target = select_speaker(speakers, selection, group_name, transport_map)
        return target, transport_map

    def apply_measured_delay(self, delay_ms, speaker, rel_str, transport_state, locked=True):
        delay_ms = max(0, min(8000, int(round(delay_ms))))
        with self.lock:
            previous = self.info["auto_delay_ms"]
            self.persisted_delay_ms = delay_ms
            self.info.update(
                state="locked" if locked else "measuring",
                speaker_name=speaker["name"],
                speaker_uuid=speaker["uuid"],
                speaker_ip=speaker["ip"],
                transport_state=transport_state,
                rel_time=rel_str,
                auto_delay_ms=delay_ms,
                locked=locked,
            )
        if self.diagnostic is not None:
            self.diagnostic.add(
                "speaker_sync",
                speaker=speaker["name"],
                auto_delay_ms=delay_ms,
                rel_time=rel_str,
                transport=transport_state,
                locked=locked,
            )
        self._save_cache(speaker_ip=speaker["ip"], auto_delay_ms=delay_ms)
        if self.on_delay is not None and delay_ms != previous:
            self.on_delay(delay_ms)

    async def measure_once(self):
        with self.lock:
            selection = self.selection
            stream_start = self.stream_start_at
            locked = self.info["locked"]
        if selection.lower() in {"off", "none", "false", "disabled"}:
            return 2.0

        target, transport_map = await self.resolve_target_speaker()
        if target is None:
            with self.lock:
                self.info.update(state="searching", speaker_name="", transport_state="", rel_time="")
            return 3.0

        info = transport_map.get(target["uuid"])
        if not info:
            try:
                info = await self.query_transport_and_position(target["ip"], target["port"])
            except Exception:
                with self.lock:
                    self.speakers = []
                    self.info.update(state="reconnecting", locked=False)
                return 2.0

        state = info.get("state") or ""
        rel_str = info.get("rel_str") or ""
        rel_s = info.get("rel_s")
        now = info.get("sampled_at") or time.monotonic()

        with self.lock:
            self.info.update(
                speaker_name=target["name"],
                speaker_uuid=target["uuid"],
                speaker_ip=target["ip"],
                transport_state=state,
                rel_time=rel_str,
            )

        if stream_start is None or state not in {"PLAYING", "TRANSITIONING"}:
            with self.lock:
                self.info["state"] = "buffering" if state == "TRANSITIONING" else "ready"
            return 0.25 if stream_start is not None else 2.5

        if state == "TRANSITIONING":
            elapsed_ms = max(self.persisted_delay_ms or 3500, int((now - stream_start) * 1000))
            self.apply_measured_delay(min(6000, elapsed_ms), target, rel_str, state, locked=False)
            return 0.08

        if rel_s is None:
            return 1.0

        raw_delta = (now - stream_start) - rel_s
        if raw_delta < 0.0:
            if now - stream_start < 8.0:
                return 0.08
            fallback = self.persisted_delay_ms or (3800 if "/ugp/" in (info.get("uri") or "").lower() else 0)
            if fallback > 0:
                self.apply_measured_delay(fallback, target, rel_str, state, locked=True)
            return 5.0

        if raw_delta > 8.0:
            return 2.0

        if locked and abs(raw_delta * 1000 - self.info["auto_delay_ms"]) < 450:
            return 6.0

        prev_rel = rel_s
        prev_at = now
        for _ in range(28):
            await asyncio.sleep(0.045)
            probe = await self.query_transport_and_position(target["ip"], target["port"])
            cur_rel = probe.get("rel_s")
            cur_at = probe.get("sampled_at") or time.monotonic()
            if probe.get("state") != "PLAYING" or cur_rel is None:
                break
            if cur_rel == prev_rel + 1 and cur_rel >= 1:
                tick_at = (prev_at + cur_at) / 2
                with self.lock:
                    current_start = self.stream_start_at
                if current_start is not None:
                    exact_delay_s = (tick_at - current_start) - cur_rel
                    if 0.05 <= exact_delay_s <= 8.0:
                        self.apply_measured_delay(
                            exact_delay_s * 1000,
                            target,
                            probe.get("rel_str") or rel_str,
                            "PLAYING",
                            locked=cur_rel >= 1,
                        )
                        return 0.25 if cur_rel < 2 else 6.0
                break
            prev_rel, prev_at = cur_rel, cur_at

        if 0.1 <= raw_delta <= 8.0 and not locked:
            self.apply_measured_delay(raw_delta * 1000, target, rel_str, state, locked=False)
        return 0.5

    async def run(self, stopping_event):
        if not self.candidate_subnets() and not self.candidate_endpoints():
            return
        while not stopping_event.is_set():
            try:
                wait_s = await self.measure_once()
            except Exception as exc:
                LOG.debug("Speaker sync poll skipped (%s)", type(exc).__name__)
                wait_s = 2.0
            deadline = time.monotonic() + max(0.05, wait_s)
            while time.monotonic() < deadline and not stopping_event.is_set():
                if self.wake.is_set():
                    self.wake.clear()
                    break
                await asyncio.sleep(0.05)
