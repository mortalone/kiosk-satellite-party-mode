import json
import sys
import threading
import time
import unittest
import urllib.error
import urllib.request
from http.server import ThreadingHTTPServer
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from bridge import Bridge, frame_colors, handler_for, open_device, validate_bands, validate_control


def eventually(predicate, timeout=2):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if predicate():
            return
        time.sleep(0.01)
    raise AssertionError("Condition was not satisfied")


class FakeDevice:
    curr_mode = "movie"
    num_leds = 12

    def __init__(self):
        self.modes, self.frames, self.brightness = [], [], []

    def get_brightness(self):
        return {"mode": "enabled", "value": 73}

    def set_mode(self, mode):
        self.modes.append(mode)

    def set_brightness(self, value, enabled=True):
        self.brightness.append((value, enabled))

    def make_pixel(self, *rgb):
        return bytes(rgb)

    def show_rt_frame(self, frame):
        self.frames.append(frame)


class BehaviorTest(unittest.TestCase):
    def test_validation(self):
        for bands in ([], [float("nan")], [True], ["1"], list(range(129))):
            with self.assertRaises(ValueError):
                validate_bands({"bands": bands})
        self.assertEqual(validate_bands({"bands": [-1, 0.3, 2]}), [0, 0.3, 1])
        for control in ({"mode": "firmware"}, {"speed": float("inf")}, {"brightness": 101}, {"color": "red"}):
            with self.assertRaises(ValueError):
                validate_control(control)

    def test_individual_leds_and_stale_audio(self):
        colors = frame_colors("chase", 12, 0, (255, 0, 0), [])
        self.assertGreater(len(set(colors)), 1)
        self.assertEqual(frame_colors("music", 2, 0, (0, 0, 0), [1, 0])[-1], (0, 0, 0))
        device = FakeDevice()
        bridge = Bridge({"device_ip": "192.168.1.10", "fps": 30}, lambda _: device)
        bridge.thread.start()
        try:
            time.sleep(0.05)
            self.assertFalse(device.frames)  # startup leaves device alone
            bridge.audio({"bands": [1, 0.5]})
            bridge.control({"mode": "music"})
            eventually(lambda: len(device.frames) >= 2)
            self.assertTrue(any(any(pixel) for pixel in device.frames[-1]))
            with bridge.lock:
                bridge.bands_at = time.monotonic() - 2
            eventually(lambda: not any(any(pixel) for pixel in device.frames[-1]))
            bridge.control({"mode": "restore"})
            eventually(lambda: device.modes == ["movie"])
            self.assertEqual(device.brightness[-1], (73, True))
        finally:
            bridge.stop()
        self.assertFalse(bridge.thread.is_alive())

    def test_connection_failure_is_reported(self):
        def fail(_host):
            raise OSError("Device unreachable")
        bridge = Bridge({"device_ip": "192.168.1.10"}, fail)
        bridge.thread.start()
        try:
            bridge.control({"mode": "rainbow"})
            eventually(lambda: "unreachable" in bridge.status()["error"])
            self.assertFalse(bridge.status()["connected"])
        finally:
            bridge.stop()

    def test_color_patch_preserves_effect_and_off_to_chase(self):
        device = FakeDevice()
        bridge = Bridge({"device_ip": "192.168.1.10", "fps": 30}, lambda _: device)
        bridge.thread.start()
        try:
            bridge.control({"mode": "chase"})
            eventually(lambda: len(device.frames) > 1)
            changed = bridge.control({"color": "#00ff00"})
            self.assertEqual(changed["mode"], "chase")
            eventually(lambda: any(p[1] and not p[0] and not p[2] for p in device.frames[-1]))
            bridge.control({"mode": "color"})
            eventually(lambda: all(p == b"\x00\xff\x00" for p in device.frames[-1]))
            bridge.control({"mode": "off"})
            eventually(lambda: device.modes == ["off"])
            count = len(device.frames)
            bridge.control({"mode": "chase"})
            eventually(lambda: len(device.frames) >= count + 3)
            self.assertNotEqual(device.frames[-1], device.frames[-3], "chase must animate after off")
        finally:
            bridge.stop()

    def test_party_patterns_are_bounded_and_silence_is_dark(self):
        for pattern in ("spectrum", "mirror", "pulse", "wave", "particles", "tunnel"):
            with self.subTest(pattern=pattern):
                pixels = frame_colors("music", 100, 0.3, (0, 255, 0), [0.2, 0.5, 1], pattern, 0.5, 1)
                self.assertEqual(len(pixels), 100)
                self.assertTrue(all(0 <= c <= 255 for pixel in pixels for c in pixel))
                self.assertTrue(all(pixel == (0, 0, 0) for pixel in frame_colors("music", 12, 0.2, (255, 255, 255), [], pattern)))
        mirror = frame_colors("music", 100, 0.2, (0, 255, 0), [0.2, 0.5, 1], "mirror")
        self.assertEqual(mirror, list(reversed(mirror)))

    def test_real_library_uses_timeout_during_authentication(self):
        from requests.adapters import HTTPAdapter
        from requests.exceptions import ConnectTimeout
        observed = []
        def send(_adapter, request, **kwargs):
            observed.append((request.url, kwargs.get("timeout")))
            raise ConnectTimeout("test")
        with patch.object(HTTPAdapter, "send", send):
            with self.assertRaises(ConnectTimeout):
                open_device("192.168.1.10")
        self.assertTrue(observed[0][0].endswith("/login"))
        self.assertEqual(observed[0][1], (2, 3))

    def test_installed_xled_plus_patterns(self):
        from xled_plus.highcontrol import HighControlInterface
        device = HighControlInterface.__new__(HighControlInterface)
        device.led_bytes = 3
        self.assertEqual(device.make_pixel(1, 2, 3), b"\x01\x02\x03")
        device.led_bytes = 4
        self.assertEqual(device.make_pixel(1, 2, 3), b"\x00\x01\x02\x03")


class ApiTest(unittest.TestCase):
    def setUp(self):
        self.bridge = Bridge({"api_token": "test-secret"})
        self.server = ThreadingHTTPServer(("127.0.0.1", 0), handler_for(self.bridge))
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.url = f"http://127.0.0.1:{self.server.server_port}"

    def tearDown(self):
        self.server.shutdown()
        self.server.server_close()
        self.thread.join()

    def request(self, path, data=None, token="test-secret", extra_headers=None):
        headers = {"Authorization": "Bearer " + token, "Content-Type": "application/json"}
        headers.update(extra_headers or {})
        request = urllib.request.Request(self.url + path, data=json.dumps(data).encode() if data is not None else None, headers=headers)
        try:
            with urllib.request.urlopen(request, timeout=2) as response:
                return response.status, json.load(response)
        except urllib.error.HTTPError as error:
            return error.code, json.load(error)

    def test_authentication_and_ingress_header_spoof(self):
        self.assertEqual(self.request("/api/status", token="wrong")[0], 401)
        self.assertEqual(self.request("/api/control", {"mode": "off"}, token="", extra_headers={"X-Ingress-Path": "/"})[0], 401)
        self.bridge.token = ""
        self.assertEqual(self.request("/api/status", token="")[0], 401)

    def test_audio_mailbox_and_control(self):
        self.assertEqual(self.request("/api/control", {"mode": "music"})[0], 202)
        self.assertEqual(self.request("/api/audio", {"bands": [0.1, 0.7]})[0], 202)
        self.assertTrue(self.request("/api/status")[1]["audio_fresh"])
        self.assertEqual(self.request("/api/audio", {"bands": []})[0], 400)
        self.assertEqual(self.request("/api/control", {"mode": "unknown"})[0], 400)
        self.assertEqual(self.request("/api/control", [1])[0], 400)
        self.assertEqual(self.request("/api/unknown", {})[0], 404)

    def test_ingress_rejects_other_peers_even_with_api_token(self):
        ingress = ThreadingHTTPServer(("127.0.0.1", 0), handler_for(self.bridge, ingress=True))
        thread = threading.Thread(target=ingress.serve_forever, daemon=True)
        thread.start()
        try:
            old_url = self.url
            self.url = f"http://127.0.0.1:{ingress.server_port}"
            self.assertEqual(self.request("/")[0], 403)
            self.assertEqual(self.request("/api/control", {"mode": "off"})[0], 401)
            self.url = old_url
        finally:
            ingress.shutdown()
            ingress.server_close()
            thread.join()


if __name__ == "__main__":
    unittest.main()
