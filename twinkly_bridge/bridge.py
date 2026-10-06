"""One device owner, bounded network I/O, and a latest-frame music mailbox."""
import colorsys
import io
from PIL import Image
import hmac
import ipaddress
import json
import logging
import math
import signal
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

LOG = logging.getLogger("twinkly_bridge")
MODES = {"color", "rainbow", "chase", "music", "off", "restore", "mood"}
PATTERNS = {"spectrum", "mirror", "pulse", "wave", "particles", "tunnel"}


def validate_control(data):
    mode = data.get("mode")
    if mode is not None and mode not in MODES:
        raise ValueError("Unknown mode")
    result = {"mode": mode} if mode is not None else {}
    if "cover_colors" in data:
        if not isinstance(data["cover_colors"], bool): raise ValueError("cover_colors must be boolean")
        result["cover_colors"] = data["cover_colors"]
    if "pattern" in data:
        if data["pattern"] not in PATTERNS:
            raise ValueError("Unknown music pattern")
        result["pattern"] = data["pattern"]
    for key, low, high in (("brightness", 0, 100), ("speed", 0.1, 5), ("gain", 0.5, 3), ("punch", 0, 100)):
        if key in data:
            value = float(data[key])
            if not math.isfinite(value) or not low <= value <= high:
                raise ValueError(f"{key} must be {low}..{high}")
            result[key] = int(value) if key == "brightness" else value
    if "color" in data:
        value = data["color"]
        if not isinstance(value, str) or len(value) != 7 or value[0] != "#":
            raise ValueError("Color must be #RRGGBB")
        result["color"] = tuple(int(value[i:i+2], 16) for i in (1, 3, 5))
    return result


def validate_bands(data):
    bands = data.get("bands")
    if not isinstance(bands, list) or not 1 <= len(bands) <= 128:
        raise ValueError("Supply 1..128 spectrum bands in range 0..1")
    result = []
    for value in bands:
        if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
            raise ValueError("Bands must be finite numbers")
        result.append(max(0.0, min(1.0, value)))
    return result


class MusicDynamics:
    """Frame-rate independent smoothing and onset pulse, without a beat clock."""
    def __init__(self):
        self.bands = []
        self.previous = None
        self.pulse = 0.0

    def process(self, bands, loudness, peak, gain, punch, dt):
        if not bands:
            self.__init__()
            return [], 0.0, 0.0, 1.0
        amount = punch / 100
        dt = max(0.001, min(0.25, dt))
        # Sendspin levels are log-scaled: measure relative amplitude changes
        # before gain so raising sensitivity cannot flatten the pulse detector.
        bass = sum(bands[:max(1, len(bands)//4)]) / max(1, len(bands)//4)
        energy = max(loudness, sum(bands)/len(bands), bass)
        signal = 10 ** (3 * (energy - 1)) if energy > 0 else 0.0
        onset = 0.0 if self.previous is None else min(1.0, max(0.0, (signal-self.previous)/max(0.015, self.previous))*2)
        self.previous = signal if self.previous is None else self.previous + (signal-self.previous)*(1-math.exp(-dt/0.2))
        self.pulse = max(self.pulse * math.exp(-dt/(0.4-0.28*amount)), onset, min(1.0, peak))
        if len(self.bands) != len(bands):
            self.bands = [0.0]*len(bands)
        # Soft gain retains differences instead of clipping every strong band.
        boost = lambda value: 1-(1-max(0.0,min(1.0,value)))**gain
        for i, value in enumerate(bands):
            target = boost(value)
            tau = (0.12-0.095*amount) if target > self.bands[i] else (0.75-0.65*amount)
            self.bands[i] += (target-self.bands[i])*(1-math.exp(-dt/tau))
        modulation = (1-amount) + amount*(0.1+0.9*self.pulse)
        return list(self.bands), boost(loudness), self.pulse, modulation


def artwork_palette(data):
    """Small, bounded image processing; ignore near-black/white margins when possible."""
    if not data: return []
    if len(data) > 262144: raise ValueError("Artwork exceeds 256 KiB")
    with Image.open(io.BytesIO(data)) as image:
        if image.width * image.height > 262144: raise ValueError("Artwork resolution too large")
        image.thumbnail((32, 32)); image = image.convert("RGB")
        quantized = image.quantize(colors=8, method=Image.Quantize.MEDIANCUT)
        palette = quantized.getpalette(); candidates = []
        for count, index in quantized.getcolors():
            rgb = tuple(palette[index*3:index*3+3]); high, low = max(rgb), min(rgb)
            score = count * (0.25 + (high-low)/255)
            if high < 24 or low > 235: score *= 0.05
            candidates.append((score, rgb))
        candidates.sort(reverse=True)
        return [rgb for _, rgb in candidates[:3]]


def palette_color(palette, position):
    index = max(0, min(1, position)) * (len(palette)-1)
    left = int(index); right = min(len(palette)-1, left+1); mix = index-left
    return tuple(round(a+(b-a)*mix) for a, b in zip(palette[left], palette[right]))


def frame_colors(mode, count, phase, color, bands, pattern="spectrum", loudness=0, peak=0,
                 punch=0, pulse=0, modulation=1, palette=None):
    energy = max(loudness, sum(bands) / len(bands) if bands else 0)
    bass = sum(bands[:max(1, len(bands)//4)]) / max(1, len(bands)//4) if bands else 0
    def pixel(i):
        fraction = i / max(1, count - 1)
        if mode == "mood":
            return palette_color(palette, fraction) if palette else color
        if mode == "color":
            return color
        if mode == "chase":
            intensity = max(0.0, 1 - ((fraction - phase) % 1) * 8)
            return tuple(round(c * intensity) for c in color)
        if mode == "music":
            position = abs(2 * i - (count - 1)) / max(1, count - 1) if pattern == "mirror" else fraction
            level = bands[min(len(bands)-1, int(position * len(bands)))] if bands else 0
            if pattern == "pulse":
                level = max(bass, energy)*(1-punch/100) + pulse*(punch/100)
            elif pattern == "wave":
                level = energy * (0.25 + 0.75 * (0.5 + 0.5 * math.sin(fraction * 12 - phase * 20)))
            elif pattern == "particles":
                sparkle = max(0, math.sin(i * 17.31 + math.floor(phase * 30) * 7.13)) ** 16
                level = max(peak, energy) * sparkle
            elif pattern == "tunnel":
                distance = abs(fraction * 2 - 1)
                level = energy * max(0, 1 - ((distance - phase * 2) % 1) * 6)
            if pattern != "pulse":
                level *= modulation
            if palette:
                tint = palette_color(palette, position)
                return tuple(round(c * min(1, max(0, level))) for c in tint)
            if pattern in {"pulse", "wave", "particles", "tunnel"}:
                return tuple(round(c * min(1, max(0, level))) for c in color)
            rgb = colorsys.hsv_to_rgb(0.72 - 0.72 * position, 1, min(1, max(0, level)))
        else:
            rgb = colorsys.hsv_to_rgb((fraction + phase) % 1, 1, 1)
        return tuple(round(c * 255) for c in rgb)
    return [pixel(i) for i in range(count)]


def open_device(host):
    from requests.adapters import HTTPAdapter
    from xled_plus.highcontrol import HighControlInterface

    class BoundedAdapter(HTTPAdapter):
        def send(self, request, **kwargs):
            if kwargs.get("timeout") is None:
                kwargs["timeout"] = (2, 3)
            return super().send(request, **kwargs)

    class Device(HighControlInterface):
        def set_mode(self, mode):
            # xled 0.7.0 does not accept modern 'color' in its Python assertion.
            response = self.session.post("led/mode", json={"mode": mode})
            self.check_response(response)
            self.curr_mode = mode
            self.last_rt_time = time.time()

        @staticmethod
        def check_response(response):
            response.raise_for_status()
            payload = response.json()
            if payload.get("code") != 1000:
                raise RuntimeError(f"Twinkly rejected command (code {payload.get('code')})")

        def set_brightness(self, brightness, enabled=True):
            response = self.session.post("led/out/brightness", json={"value": brightness, "type": "A", "mode": "enabled" if enabled else "disabled"})
            self.check_response(response)

        def ensure_rt(self, force=False):
            actual = self.get_mode()["mode"]
            recovered = actual != "rt" and self.curr_mode == "rt"
            if force or actual != "rt":
                self.set_mode("rt")
            return recovered

        def get_mode(self):
            result = super().get_mode()
            result.raise_for_status()
            return result

        @property
        def session(self):
            session = super().session
            if not getattr(session, "bridge_bounded", False):
                session.mount("http://", BoundedAdapter())
                session.trust_env = False
                session.bridge_bounded = True
            return session

    return Device(host)


class Bridge:
    def __init__(self, options, factory=open_device):
        self.host = options.get("device_ip", "").strip()
        if self.host:
            address = ipaddress.ip_address(self.host)
            if address.version != 4 or address.is_multicast or address.is_unspecified:
                raise ValueError("device_ip must be the Twinkly IPv4 address")
        self.token = options.get("api_token", "")
        self.fps = max(5, min(30, int(options.get("fps", 20))))
        self.settings = {"mode": "restore", "brightness": int(options.get("brightness", 30)),
                         "speed": float(options.get("speed", 1)), "color": (255, 64, 128),
                         "cover_colors": options.get("cover_colors", False),
                         "pattern": options.get("music_pattern", "mirror"), "gain": 1.0,
                         "punch": validate_control({"punch": options.get("music_punch", 50)})["punch"]}
        self.factory = factory
        self.lock = threading.Lock()
        self.wake = threading.Event()
        self.stopping = threading.Event()
        self.revision = 0
        self.bands, self.bands_at = [], 0
        self.loudness, self.peak = 0.0, 0.0
        self.info = {"connected": False, "leds": 0, "error": "", "applied_mode": "restore", "recoveries": 0}
        self.cover_data = None
        self.cover_palette = []
        self.sendspin = None
        self.thread = threading.Thread(target=self.run, daemon=True)

    def artwork(self, data):
        if len(data) > 262144: return
        with self.lock:
            self.cover_data = bytes(data)
        self.wake.set()

    def control(self, data):
        update = validate_control(data)
        with self.lock:
            self.settings.update(update)
            self.revision += 1
        self.wake.set()
        return self.status()

    def audio(self, data):
        bands = validate_bands(data)
        with self.lock:
            self.bands, self.bands_at = bands, time.monotonic()

    def visualization(self, bands=None, loudness=None, peak=None):
        with self.lock:
            if bands is not None:
                self.bands, self.bands_at = bands, time.monotonic()
            if loudness is not None:
                self.loudness = loudness
            if peak is not None:
                self.peak = peak

    def clear_audio(self):
        with self.lock:
            self.bands, self.bands_at, self.loudness, self.peak = [], 0, 0, 0

    def status(self):
        with self.lock:
            result = {**self.info, "device_ip": self.host, "mode": self.settings["mode"],
                    "brightness": self.settings["brightness"], "fps": self.fps,
                    "speed": self.settings["speed"],
                    "pattern": self.settings["pattern"], "gain": self.settings["gain"],
                    "punch": self.settings["punch"],
                    "color": "#" + "".join(f"{c:02x}" for c in self.settings["color"]),
                    "cover_colors": self.settings["cover_colors"],
                    "cover_palette": ["#"+"".join(f"{c:02x}" for c in rgb) for rgb in self.cover_palette],
                    "revision": self.revision,
                    "audio_fresh": time.monotonic() - self.bands_at < 1.5}
        result["sendspin"] = self.sendspin.status() if self.sendspin else {"connected": False, "state": "disabled"}
        return result

    def run(self):
        mode = "restore"
        palette = []; target_palette = []
        device, original, applied_revision = None, None, -1
        last_brightness = None
        next_retry = 0
        next_rt_check = 0
        dynamics = MusicDynamics()
        last_frame = time.monotonic()
        try:
            while not self.stopping.is_set():
                self.wake.clear()
                with self.lock:
                    cover_data, self.cover_data = self.cover_data, None
                    settings, revision = dict(self.settings), self.revision
                    applied_mode = self.info["applied_mode"]
                    bands = list(self.bands) if time.monotonic() - self.bands_at < 1.5 else []
                    loudness, peak = (self.loudness, self.peak) if bands else (0, 0)
                    self.peak *= 0.85
                if cover_data is not None:
                    try:
                        target_palette = artwork_palette(cover_data)
                        if not target_palette: palette = []
                        with self.lock: self.cover_palette = target_palette
                    except (ValueError, OSError) as error:
                        LOG.warning("Artwork ignored: %s", error)
                if target_palette:
                    if not palette: palette = list(target_palette)
                    else:
                        palette = [tuple(a+(b-a)*0.04 for a,b in zip(palette[min(i,len(palette)-1)],rgb)) for i,rgb in enumerate(target_palette)]
                mode = settings["mode"]
                if mode == "restore" and device is None:
                    self.wake.wait(0.2)
                    continue
                if time.monotonic() < next_retry:
                    self.wake.wait(0.2)
                    continue
                try:
                    if device is None:
                        if not self.host:
                            raise ValueError("Set device_ip in the add-on configuration first")
                        device = self.factory(self.host)
                        # Do not restore realtime: another sender may have stopped.
                        if original is None:
                            original = {"mode": device.curr_mode if device.curr_mode != "rt" else "off",
                                        "brightness": dict(device.get_brightness())}
                        with self.lock:
                            self.info.update(connected=True, leds=device.num_leds, error="")
                    if mode == "restore":
                        if revision != applied_revision:
                            self.restore(device, original)
                            last_brightness = None
                    elif mode == "off":
                        if revision != applied_revision:
                            device.set_mode("off")
                    else:
                        if last_brightness != settings["brightness"]:
                            device.set_brightness(settings["brightness"])
                            last_brightness = settings["brightness"]
                        if hasattr(device, "ensure_rt") and (time.monotonic() >= next_rt_check or mode != applied_mode):
                            recovered = device.ensure_rt(force=mode != applied_mode)
                            if recovered:
                                with self.lock:
                                    self.info["recoveries"] += 1
                            next_rt_check = time.monotonic() + 2
                        now = time.monotonic()
                        dt, last_frame = now-last_frame, now
                        phase = now * settings["speed"] * (1+0.7*settings["punch"]/100 if mode == "music" else 1) / 6
                        if mode != "music":
                            dynamics = MusicDynamics()
                        smooth, level, pulse, modulation = dynamics.process(bands, loudness, peak,
                            settings["gain"], settings["punch"], dt)
                        colors = frame_colors(mode, device.num_leds, phase, settings["color"], smooth,
                                              settings["pattern"], level, peak,
                                              settings["punch"], pulse, modulation,
                                              palette if settings["cover_colors"] or mode == "mood" else None)
                        device.show_rt_frame([device.make_pixel(*rgb) for rgb in colors])
                    applied_revision = revision
                    with self.lock:
                        self.info.update(error="", applied_mode=mode)
                except Exception as exc:
                    LOG.warning("Twinkly control failed: %s", exc)
                    with self.lock:
                        self.info.update(connected=False, error=str(exc))
                    self.close_device(device)
                    device, last_brightness = None, None
                    applied_revision = -1
                    next_retry = time.monotonic() + 5
                self.wake.wait(1 / self.fps if mode not in {"restore", "off"} else 0.2)
        finally:
            if device is not None and original is not None and mode != "restore":
                try:
                    self.restore(device, original)
                except Exception:
                    LOG.warning("Could not restore device on shutdown")
            self.close_device(device)

    @staticmethod
    def restore(device, original):
        brightness = original["brightness"]
        device.set_brightness(brightness.get("value", 100), enabled=brightness.get("mode") != "disabled")
        device.set_mode(original["mode"])

    @staticmethod
    def close_device(device):
        if device is not None:
            session = getattr(device, "_session", None)
            if session is not None:
                session.close()
            udp = getattr(device, "_udpclient", None)
            if udp is not None:
                udp.close()

    def stop(self):
        self.stopping.set()
        self.wake.set()
        self.thread.join(timeout=10)


def handler_for(bridge, ingress=False):
    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *_args):
            pass

        def reply(self, code, payload, content_type="application/json"):
            body = json.dumps(payload, allow_nan=False).encode() if content_type == "application/json" else payload
            self.send_response(code)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store")
            self.send_header("X-Content-Type-Options", "nosniff")
            self.end_headers()
            self.wfile.write(body)

        def authorized(self):
            # Supervisor ingress proxy has this fixed peer address. Never trust a caller's header.
            if ingress:
                return self.client_address[0] == "172.30.32.2"
            supplied = self.headers.get("Authorization", "")
            return bool(bridge.token) and hmac.compare_digest(supplied.encode(), ("Bearer " + bridge.token).encode())

        def do_GET(self):
            if ingress and not self.authorized():
                self.reply(403, {"error": "Use Home Assistant ingress"})
            elif self.path == "/" and ingress:
                self.reply(200, Path(__file__).with_name("index.html").read_bytes(), "text/html; charset=utf-8")
            elif self.path == "/ui.js" and ingress:
                self.reply(200, Path(__file__).with_name("ui.js").read_bytes(), "text/javascript; charset=utf-8")
            elif self.path == "/health":
                self.reply(200, {"running": True})
            elif self.path == "/api/status" and self.authorized():
                self.reply(200, bridge.status())
            else:
                self.reply(401, {"error": "Authentication required"})

        def do_POST(self):
            if not self.authorized():
                self.reply(401, {"error": "Authentication required"})
                return
            try:
                size = int(self.headers.get("Content-Length", "0"))
                if not 0 < size <= 8192:
                    raise ValueError("Invalid request size")
                data = json.loads(self.rfile.read(size))
                if not isinstance(data, dict):
                    raise ValueError("Expected an object")
                if self.path == "/api/control":
                    status = bridge.control(data)
                    self.reply(202, status)
                    return
                elif self.path == "/api/audio":
                    bridge.audio(data)
                else:
                    self.reply(404, {"error": "Unknown endpoint"})
                    return
                self.reply(202, {"accepted": True})
            except (ValueError, TypeError, OverflowError) as exc:
                self.reply(400, {"error": str(exc)})

        def setup(self):
            super().setup()
            self.connection.settimeout(5)

    return Handler


def main():
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s [%(name)s] %(message)s")
    options = json.loads(Path("/data/options.json").read_text())
    bridge = Bridge(options)
    from sendspin_source import SendspinSource
    bridge.sendspin = SendspinSource(bridge, options)
    server = ThreadingHTTPServer(("0.0.0.0", 8099), handler_for(bridge, ingress=True))
    api = ThreadingHTTPServer(("0.0.0.0", 8100), handler_for(bridge))
    server.daemon_threads = True
    api.daemon_threads = True
    bridge.thread.start()
    bridge.sendspin.start()
    api_thread = threading.Thread(target=api.serve_forever, daemon=True)
    api_thread.start()
    def shutdown(*_args):
        threading.Thread(target=server.shutdown, daemon=True).start()
    signal.signal(signal.SIGTERM, shutdown)
    signal.signal(signal.SIGINT, shutdown)
    try:
        LOG.info("Twinkly Bridge ready; open the web UI to test your device")
        server.serve_forever()
    finally:
        server.server_close()
        api.shutdown()
        api.server_close()
        bridge.sendspin.stop()
        bridge.stop()


if __name__ == "__main__":
    main()
