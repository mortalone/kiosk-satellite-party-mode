import asyncio
import sys
import tempfile
import threading
import time
import unittest
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from speaker_sync import SpeakerSync, parse_rel_time, parse_zone_groups, select_speaker


SAMPLE_ZGS_SOAP = """<?xml version="1.0" encoding="utf-8"?>
<s:Envelope xmlns:s="http://schemas.xmlsoap.org/soap/envelope/">
<s:Body><u:GetZoneGroupStateResponse xmlns:u="urn:schemas-upnp-org:service:ZoneGroupTopology:1">
<ZoneGroupState>&lt;ZoneGroupState&gt;&lt;ZoneGroups&gt;
&lt;ZoneGroup Coordinator=&quot;RINCON_KITCHEN1400&quot; ID=&quot;RINCON_KITCHEN1400:1&quot;&gt;
&lt;ZoneGroupMember UUID=&quot;RINCON_KITCHEN_RIGHT&quot; Location=&quot;http://192.168.0.216:1400/xml/device_description.xml&quot; ZoneName=&quot;Stueetagen (Sonos)&quot; Invisible=&quot;1&quot;/&gt;
&lt;ZoneGroupMember UUID=&quot;RINCON_KITCHEN1400&quot; Location=&quot;http://192.168.0.44:1400/xml/device_description.xml&quot; ZoneName=&quot;Stueetagen (Sonos)&quot;/&gt;
&lt;/ZoneGroup&gt;
&lt;ZoneGroup Coordinator=&quot;RINCON_GARDEN1400&quot; ID=&quot;RINCON_GARDEN1400:2&quot;&gt;
&lt;ZoneGroupMember UUID=&quot;RINCON_GARDEN1400&quot; Location=&quot;http://192.168.0.230:1400/xml/device_description.xml&quot; ZoneName=&quot;Have&quot;/&gt;
&lt;/ZoneGroup&gt;
&lt;/ZoneGroups&gt;&lt;/ZoneGroupState&gt;</ZoneGroupState>
</u:GetZoneGroupStateResponse></s:Body></s:Envelope>"""


class SpeakerSyncTest(unittest.IsolatedAsyncioTestCase):
    def test_parse_rel_time_and_zone_groups(self):
        self.assertEqual(parse_rel_time("0:00:00"), 0.0)
        self.assertEqual(parse_rel_time("0:01:34"), 94.0)
        self.assertEqual(parse_rel_time("1:02:03.5"), 3723.5)
        self.assertIsNone(parse_rel_time("NOT_IMPLEMENTED"))
        self.assertIsNone(parse_rel_time(""))

        speakers = parse_zone_groups(SAMPLE_ZGS_SOAP)
        self.assertEqual(len(speakers), 2)
        self.assertEqual(speakers[0]["name"], "Have")
        self.assertEqual(speakers[1]["uuid"], "RINCON_KITCHEN1400")
        self.assertEqual(speakers[1]["name"], "Stueetagen (Sonos)")
        self.assertEqual(speakers[1]["ip"], "192.168.0.44")

    def test_select_speaker_auto_and_rename_resilience(self):
        speakers = parse_zone_groups(SAMPLE_ZGS_SOAP)
        tmap = {
            "RINCON_GARDEN1400": {"state": "STOPPED", "uri": ""},
            "RINCON_KITCHEN1400": {
                "state": "PLAYING",
                "uri": "x-rincon-mp3radio://http://192.168.0.18:8097/ugp/ugp_test.mp3",
            },
        }
        chosen = select_speaker(speakers, "auto", group_name="", transport_map=tmap)
        self.assertEqual(chosen["uuid"], "RINCON_KITCHEN1400")

        # Even if the user renames the speaker in Sonos and its IP changes, UUID selection still matches
        renamed = [{"uuid": "RINCON_KITCHEN1400", "name": "Køkken Alrum Ny", "ip": "192.168.0.99", "port": 1400}]
        self.assertEqual(select_speaker(renamed, "RINCON_KITCHEN1400")["name"], "Køkken Alrum Ny")
        self.assertEqual(select_speaker(renamed, "Køkken")["uuid"], "RINCON_KITCHEN1400")
        self.assertIsNone(select_speaker(renamed, "off"))

    async def test_live_upnp_tick_lock_and_persistence(self):
        state = {"transport": "TRANSITIONING", "start_mono": time.monotonic()}

        class UpnpHandler(BaseHTTPRequestHandler):
            def log_message(self, *_args):
                pass

            def do_POST(self):
                action = self.headers.get("SOAPAction", "")
                if "GetZoneGroupState" in action:
                    port = self.server.server_port
                    xml = SAMPLE_ZGS_SOAP.replace("192.168.0.44:1400", f"127.0.0.1:{port}")
                elif "GetTransportInfo" in action:
                    xml = f"<s:Envelope><s:Body><CurrentTransportState>{state['transport']}</CurrentTransportState></s:Body></s:Envelope>"
                else:
                    elapsed = max(0, int(time.monotonic() - state["start_mono"]))
                    rel = f"0:00:{elapsed:02d}"
                    xml = (
                        "<s:Envelope><s:Body>"
                        f"<RelTime>{rel}</RelTime>"
                        "<TrackURI>x-rincon-mp3radio://http://127.0.0.1:8097/ugp/ugp_1.mp3</TrackURI>"
                        "</s:Body></s:Envelope>"
                    )
                body = xml.encode("utf-8")
                self.send_response(200)
                self.send_header("Content-Type", "text/xml")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)

        server = ThreadingHTTPServer(("127.0.0.1", 0), UpnpHandler)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            with tempfile.TemporaryDirectory() as tmp:
                delays = []
                sync = SpeakerSync(
                    {"sync_speaker": f"127.0.0.1:{server.server_port}"},
                    directory=Path(tmp),
                    on_delay=delays.append,
                )
                # Stream started 3.4 seconds before Sonos starts playing
                sonos_zero = time.monotonic() - 0.85
                state["start_mono"] = sonos_zero
                sync.on_stream_start(sonos_zero - 3.4)

                # While TRANSITIONING, holds delay >= 3500ms so LEDs don't flash early
                await sync.measure_once()
                self.assertFalse(sync.status()["locked"])
                self.assertGreaterEqual(sync.status()["auto_delay_ms"], 3400)

                # Switch Sonos to PLAYING and let measure_once catch the 0:00:00 -> 0:00:01 tick
                state["transport"] = "PLAYING"
                await sync.measure_once()
                st = sync.status()
                self.assertTrue(st["locked"])
                self.assertEqual(st["speaker_name"], "Stueetagen (Sonos)")
                self.assertAlmostEqual(st["auto_delay_ms"], 3400, delta=150)

                # Verify persistence across restart
                reloaded = SpeakerSync({"sync_speaker": "auto"}, directory=Path(tmp))
                self.assertAlmostEqual(reloaded.status()["auto_delay_ms"], st["auto_delay_ms"], delta=1)
        finally:
            server.shutdown()
            server.server_close()
            thread.join()

    async def test_continuous_ugp_stream_sync(self):
        # Sonos is already mid-stream playing an ongoing UGP radio stream (rel_time: 1:19:41 = 4781s)
        state = {"transport": "PLAYING", "start_mono": time.monotonic() - 4780.85}

        class UgpHandler(BaseHTTPRequestHandler):
            def log_message(self, *_args):
                pass

            def do_POST(self):
                action = self.headers.get("SOAPAction", "")
                if "GetZoneGroupState" in action:
                    port = self.server.server_port
                    xml = SAMPLE_ZGS_SOAP.replace("192.168.0.44:1400", f"127.0.0.1:{port}")
                elif "GetTransportInfo" in action:
                    xml = f"<s:Envelope><s:Body><CurrentTransportState>{state['transport']}</CurrentTransportState></s:Body></s:Envelope>"
                else:
                    elapsed = max(0, int(time.monotonic() - state["start_mono"]))
                    m, s = divmod(elapsed, 60)
                    h, m = divmod(m, 60)
                    rel = f"{h}:{m:02d}:{s:02d}"
                    xml = (
                        "<s:Envelope><s:Body>"
                        f"<RelTime>{rel}</RelTime>"
                        "<TrackURI>x-rincon-mp3radio://http://127.0.0.1:8097/ugp/ugp_test.mp3</TrackURI>"
                        "</s:Body></s:Envelope>"
                    )
                body = xml.encode("utf-8")
                self.send_response(200)
                self.send_header("Content-Type", "text/xml")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)

        server = ThreadingHTTPServer(("127.0.0.1", 0), UgpHandler)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            with tempfile.TemporaryDirectory() as tmp:
                delays = []
                sync = SpeakerSync(
                    {"sync_speaker": f"127.0.0.1:{server.server_port}"},
                    directory=Path(tmp),
                    on_delay=delays.append,
                )
                # Twinkly Bridge starts up or track changes, stream_start_at is set to now
                now = time.monotonic()
                sync.on_stream_start(now)

                # measure_once handles negative raw_delta by aligning sub-second tick to UGP baseline
                await sync.measure_once()
                st = sync.status()
                self.assertTrue(st["locked"])
                self.assertEqual(st["state"], "locked")
                # Delay must be properly anchored within standard Sonos UGP buffer range (3.0s - 4.8s)
                self.assertGreaterEqual(st["auto_delay_ms"], 3000)
                self.assertLessEqual(st["auto_delay_ms"], 4800)
        finally:
            server.shutdown()
            server.server_close()
            thread.join()


if __name__ == "__main__":
    unittest.main()
