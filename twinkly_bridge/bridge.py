"""One device owner, bounded network I/O, and a latest-frame music mailbox."""
import colorsys
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
MODES = {"color", "rainbow", "chase", "music", "off", "restore"}


def validate_control(data):
    mode = data.get("mode", "restore")
    if mode not in MODES:
        raise ValueError("Unknown mode")
    result = {"mode": mode}
    for key, low, high in (("brightness", 0, 100), ("speed", 0.1, 5)):
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


def frame_colors(mode, count, phase, color, bands):
    def pixel(i):
        fraction = i / max(1, count - 1)
        if mode == "color":
            return color
        if mode == "chase":
            intensity = max(0.0, 1 - ((fraction - phase) % 1) * 8)
            return tuple(round(c * intensity) for c in color)
        if mode == "music":
            level = bands[min(len(bands)-1, int(fraction * len(bands)))] if bands else 0
            rgb = colorsys.hsv_to_rgb(0.72 - 0.72 * fraction, 1, level)
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
                         "speed": float(options.get("speed", 1)), "color": (255, 64, 128)}
        self.factory = factory
        self.lock = threading.Lock()
        self.wake = threading.Event()
        self.stopping = threading.Event()
        self.revision = 0
        self.bands, self.bands_at = [], 0
        self.info = {"connected": False, "leds": 0, "error": "", "applied_mode": "restore"}
        self.thread = threading.Thread(target=self.run, daemon=True)

    def control(self, data):
        update = validate_control(data)
        with self.lock:
            self.settings.update(update)
            self.revision += 1
        self.wake.set()

    def audio(self, data):
        bands = validate_bands(data)
        with self.lock:
            self.bands, self.bands_at = bands, time.monotonic()

    def status(self):
        with self.lock:
            return {**self.info, "device_ip": self.host, "mode": self.settings["mode"],
                    "brightness": self.settings["brightness"], "fps": self.fps,
                    "speed": self.settings["speed"],
                    "audio_fresh": time.monotonic() - self.bands_at < 1.5}

    def run(self):
        mode = "restore"
        device, original, applied_revision = None, None, -1
        last_brightness = None
        next_retry = 0
        try:
            while not self.stopping.is_set():
                self.wake.clear()
                with self.lock:
                    settings, revision = dict(self.settings), self.revision
                    bands = list(self.bands) if time.monotonic() - self.bands_at < 1.5 else []
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
                        phase = time.monotonic() * settings["speed"] / 6
                        colors = frame_colors(mode, device.num_leds, phase, settings["color"], bands)
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
                    bridge.control(data)
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
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    options = json.loads(Path("/data/options.json").read_text())
    bridge = Bridge(options)
    server = ThreadingHTTPServer(("0.0.0.0", 8099), handler_for(bridge, ingress=True))
    api = ThreadingHTTPServer(("0.0.0.0", 8100), handler_for(bridge))
    server.daemon_threads = True
    api.daemon_threads = True
    bridge.thread.start()
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
        bridge.stop()


if __name__ == "__main__":
    main()
