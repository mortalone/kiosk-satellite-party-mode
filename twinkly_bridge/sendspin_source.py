"""Receive timestamped visualizer data, without an audio player or local FFT."""
import asyncio
import heapq
import json
import logging
import os
import struct
import threading
import time
from dataclasses import replace
from pathlib import Path
from urllib.parse import urlsplit

from aiohttp import ClientSession, ClientTimeout, WSMsgType
from aiosendspin.client import SendspinClient
from aiosendspin.client.time_sync import SendspinTimeFilter
from aiosendspin.models.core import DeviceInfo
from aiosendspin.models.types import Roles
from aiosendspin.models.visualizer import ClientHelloVisualizerSpectrum, ClientHelloVisualizerSupport, VisualizerFrame
from aiosendspin.noise.keys import Identity, b64url_decode
from aiosendspin.noise.trust_store import FileClientPairingStore

LOG = logging.getLogger("sendspin_source")


def load_identity(directory):
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / "sendspin_identity.key"
    try:
        return Identity.from_private_bytes(b64url_decode(path.read_text().strip()))
    except FileNotFoundError:
        identity = Identity.generate()
        with os.fdopen(os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600), "w") as output:
            output.write(identity.private_b64u)
        return identity


def decode_legacy_frame(packet, bins):
    if len(packet) < 9:
        return None
    kind, timestamp = packet[0], struct.unpack(">q", packet[1:9])[0]
    payload = packet[9:]
    if kind == 19 and len(payload) == bins * 2:
        return VisualizerFrame(timestamp_us=timestamp, spectrum=list(struct.unpack(f">{bins}H", payload)))
    if kind == 16 and len(payload) == 2:
        return VisualizerFrame(timestamp_us=timestamp, loudness=struct.unpack(">H", payload)[0])
    if kind == 20 and len(payload) == 1:
        return VisualizerFrame(timestamp_us=timestamp, peak_strength=payload[0])
    return None


class FrameBuffer:
    """Bounded timeline; lookahead data is rendered at playback time, never on arrival."""
    def __init__(self, bridge, maximum=2048):
        self.bridge, self.maximum = bridge, maximum
        self.frames = []
        self.serial = 0

    def clear(self):
        self.frames.clear()
        self.bridge.clear_audio()

    def add(self, frame, due, now=None):
        now = time.monotonic() if now is None else now
        if due < now or due > now + 30 or len(self.frames) >= self.maximum:
            return False
        self.serial += 1
        heapq.heappush(self.frames, (due, self.serial, frame))
        return True

    def drain(self, now=None):
        now = time.monotonic() if now is None else now
        bands, loudness, peak = None, None, None
        count = 0
        while self.frames and self.frames[0][0] <= now:
            due, _, frame = heapq.heappop(self.frames)
            if now - due > 0.25:
                continue
            count += 1
            if frame.spectrum is not None:
                bands = [min(1.0, max(0.0, value / 65535)) for value in frame.spectrum]
            if frame.loudness is not None:
                loudness = min(1.0, max(0.0, frame.loudness / 65535))
            if frame.peak_strength is not None:
                peak = max(peak or 0, min(1.0, max(0.0, frame.peak_strength / 255)))
        if count:
            self.bridge.visualization(bands, loudness, peak)
        return count


class SendspinSource:
    def __init__(self, bridge, options, directory=Path("/data")):
        self.bridge = bridge
        self.url = options.get("sendspin_url", "").strip()
        if self.url:
            parsed = urlsplit(self.url)
            if parsed.scheme not in {"ws", "wss"} or not parsed.hostname or parsed.username or parsed.password or parsed.query or parsed.fragment:
                raise ValueError("sendspin_url must be ws://HOST:8927/sendspin or wss://… without login details or query parameters")
        self.protocol = options.get("sendspin_protocol", "auto")
        if self.protocol not in {"auto", "noise", "legacy"}:
            raise ValueError("Unknown Sendspin protocol")
        self.directory = directory
        self.delay = max(-2000, min(2000, int(options.get("light_delay_ms", 0)))) / 1000
        self.support = ClientHelloVisualizerSupport(buffer_capacity=131072, rate_max=bridge.fps,
            types=["spectrum", "loudness", "peak"],
            spectrum=ClientHelloVisualizerSpectrum(n_disp_bins=32, scale="log", f_min=40, f_max=16000))
        self.buffer = FrameBuffer(bridge)
        self.stopping = threading.Event()
        self.lock = threading.Lock()
        self.info = {"connected": False, "state": "waiting" if self.url else "disabled", "error": "",
                     "group": "", "playback": "", "frames_received": 0, "frames_rendered": 0,
                     "protocol": "", "client_id": "", "clock_synced": False}
        self.thread = threading.Thread(target=lambda: asyncio.run(self.run()), daemon=True)

    def update(self, **values):
        with self.lock:
            self.info.update(values)

    def status(self):
        with self.lock:
            return dict(self.info)

    def group_update(self, payload):
        state = getattr(payload.playback_state, "value", payload.playback_state)
        values = {}
        if payload.group_name is not None:
            values["group"] = payload.group_name
        if state is not None:
            values["playback"] = state
            if state != "playing":
                self.buffer.clear()
        self.update(**values)

    async def render(self):
        while not self.stopping.is_set():
            rendered = self.buffer.drain()
            if rendered:
                with self.lock:
                    self.info["frames_rendered"] += rendered
            await asyncio.sleep(0.01)

    def receive(self, frames, client):
        synced = client.is_time_synchronized()
        self.update(clock_synced=synced)
        if not synced:
            return
        for frame in frames:
            due = time.monotonic() + (client.compute_play_time(frame.timestamp_us) - client.now_us()) / 1e6 + self.delay
            if self.buffer.add(frame, due):
                with self.lock:
                    self.info["frames_received"] += 1

    async def modern(self, identity, store, session):
        client = SendspinClient(identity, "Twinkly Bridge", [Roles.VISUALIZER], pairing_store=store,
            visualizer_support=self.support, session=session,
            device_info=DeviceInfo(product_name="Twinkly Bridge", manufacturer="Kiosk companion", software_version="0.1.2"))
        disconnected = asyncio.Event()
        client.add_visualizer_listener(lambda frames: self.receive(frames, client))
        client.add_group_update_listener(self.group_update)
        client.add_stream_clear_listener(lambda roles: self.buffer.clear() if roles is None or any(r.startswith("visualizer") for r in roles) else None)
        client.add_stream_end_listener(lambda roles: self.buffer.clear() if roles is None or any(r.startswith("visualizer") for r in roles) else None)
        client.add_disconnect_listener(disconnected.set)
        try:
            await asyncio.wait_for(client.connect(self.url), timeout=15)
            await client.send_available(available=True)
            self.update(connected=True, state="connected", protocol="noise", error="")
            LOG.info("Sendspin connected using encrypted visualizer transport")
            while not self.stopping.is_set() and not disconnected.is_set():
                self.update(clock_synced=client.is_time_synchronized())
                await asyncio.sleep(0.2)
        finally:
            LOG.info("Sendspin connection ending (%s)", "addon stopping" if self.stopping.is_set() else "connection closed or failed")
            await client.disconnect()

    async def legacy(self, identity, session, socket=None, hello=None):
        from aiosendspin.models.core import GroupUpdateServerPayload
        if socket is None:
            socket = await session.ws_connect(self.url, heartbeat=20, max_msg_size=262144)
        clock = SendspinTimeFilter()
        synced, active, bins = False, False, 32
        now_us = lambda: time.monotonic_ns() // 1000
        await socket.send_json({"type": "client/hello", "payload": {"client_id": identity.peer_id,
            "name": "Twinkly Bridge", "version": 1, "supported_roles": ["visualizer@v1"],
            "visualizer@v1_support": self.support.to_dict(),
            "device_info": {"product_name": "Twinkly Bridge", "software_version": "0.1.2"}}})
        await socket.send_json({"type": "client/state", "payload": {"available": True, "state": "synchronized"}})
        async def synchronize():
            while not self.stopping.is_set() and not socket.closed:
                await socket.send_json({"type": "client/time", "payload": {"client_transmitted": now_us()}})
                await asyncio.sleep(1)
        timing = asyncio.create_task(synchronize())
        self.update(connected=True, state="connected", protocol="legacy", error="")
        try:
            while not self.stopping.is_set():
                try:
                    message = await socket.receive(timeout=0.5)
                except asyncio.TimeoutError:
                    continue
                if message.type == WSMsgType.TEXT:
                    data = json.loads(message.data)
                    kind, payload = data.get("type"), data.get("payload", {})
                    if kind == "server/time":
                        t1, t2, t3, t4 = payload["client_transmitted"], payload["server_received"], payload["server_transmitted"], now_us()
                        clock.update(int(((t2-t1)+(t3-t4))/2), max(1, int(((t4-t1)-(t3-t2))/2)), t4)
                        synced = True
                        self.update(clock_synced=True)
                    elif kind == "stream/start" and "visualizer" in payload:
                        config = payload["visualizer"]
                        bins = int(config.get("spectrum", {}).get("n_disp_bins", 32))
                        if not 1 <= bins <= 128:
                            raise ValueError("Invalid Sendspin spectrum size")
                        active = "spectrum" in config.get("types", [])
                    elif kind in {"stream/clear", "stream/end"}:
                        roles = payload.get("roles")
                        if roles is None or any(r.startswith("visualizer") for r in roles):
                            self.buffer.clear()
                            if kind == "stream/end":
                                active = False
                    elif kind == "group/update":
                        self.group_update(GroupUpdateServerPayload.from_dict(payload))
                elif message.type == WSMsgType.BINARY and synced and active:
                    frame = decode_legacy_frame(message.data, bins)
                    if frame is not None:
                        due = clock.compute_client_time(frame.timestamp_us) / 1e6 + self.delay
                        if self.buffer.add(frame, due):
                            with self.lock:
                                self.info["frames_received"] += 1
                elif message.type in {WSMsgType.CLOSE, WSMsgType.CLOSED, WSMsgType.ERROR}:
                    break
        finally:
            timing.cancel()
            await asyncio.gather(timing, return_exceptions=True)
            await socket.close()

    async def run(self):
        if not self.url:
            return
        renderer = asyncio.create_task(self.render())
        try:
            identity = load_identity(self.directory)
            store = await FileClientPairingStore.open(self.directory / "sendspin_pairing.json")
            # Receive-only visualization uses MA's guest approval, never audio/control roles.
            config = await store.get_pairing_config()
            await store.store_pairing_config(replace(config, unpaired_access_enabled=True))
            self.update(client_id=identity.peer_id)
            async with ClientSession(timeout=ClientTimeout(total=15, sock_connect=5)) as session:
                while not self.stopping.is_set():
                    try:
                        self.update(state="connecting", clock_synced=False)
                        if self.protocol == "legacy":
                            await self.legacy(identity, session)
                        else:
                            legacy_socket, hello = None, None
                            if self.protocol == "auto":
                                probe = await session.ws_connect(self.url, heartbeat=20, max_msg_size=262144)
                                try:
                                    first = await probe.receive(timeout=0.4)
                                    if first.type == WSMsgType.TEXT:
                                        value = json.loads(first.data)
                                        if value.get("type") == "server/hello":
                                            legacy_socket, hello = probe, value
                                except asyncio.TimeoutError:
                                    pass
                                finally:
                                    if legacy_socket is None:
                                        await probe.close()
                            if legacy_socket is not None:
                                await self.legacy(identity, session, legacy_socket, hello)
                            else:
                                await self.modern(identity, store, session)
                    except Exception as exc:
                        LOG.warning("Sendspin connection failed (%s)", type(exc).__name__)
                        # Do not expose the URL/query or credentials from library exceptions.
                        self.update(error=f"{type(exc).__name__}: Kontrollér Sendspin-adresse og protokol")
                    finally:
                        self.buffer.clear()
                        self.update(connected=False, state="reconnecting", clock_synced=False, playback="", group="")
                    for _ in range(25):
                        if self.stopping.is_set():
                            break
                        await asyncio.sleep(0.2)
        except Exception as exc:
            LOG.exception("Could not start Sendspin receiver")
            self.update(state="error", error=f"{type(exc).__name__}: Could not load Sendspin state")
        finally:
            renderer.cancel()
            await asyncio.gather(renderer, return_exceptions=True)
            self.buffer.clear()

    def start(self):
        self.thread.start()

    def stop(self):
        self.stopping.set()
        self.thread.join(timeout=17)
