"""Exercise real xled authentication, mode changes and UDP encoding against a mock controller."""
import base64
import json
import sys
import threading
import unittest
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from bridge import open_device, frame_colors, Bridge


class DeviceTest(unittest.TestCase):
    def setUp(self):
        self.mode = 'movie'
        self.fail = False
        self.commands, self.packets = [], []
        owner = self
        class Handler(BaseHTTPRequestHandler):
            def log_message(self, *_args):
                pass
            def response(self, data):
                body = json.dumps({'code':1000,**data}).encode()
                self.send_response(200);self.send_header('Content-Length',str(len(body)));self.end_headers();self.wfile.write(body)
            def do_GET(self):
                endpoint = self.path.removeprefix('/xled/v1/')
                data = {'gestalt': {'number_of_led':24,'fw_family':'N','bytes_per_led':3,'led_profile':'RGB','mac':'aa:bb:cc:dd:ee:ff'},
                        'fw/version':{'version':'2.8.0'},'led/config':{'strings':[]},
                        'led/mode':{'mode':owner.mode},'led/out/brightness':{'mode':'enabled','value':73}}
                self.response(data[endpoint])
            def do_POST(self):
                endpoint = self.path.removeprefix('/xled/v1/')
                data = json.loads(self.rfile.read(int(self.headers['Content-Length'])))
                owner.commands.append((endpoint,data))
                if endpoint == 'login':
                    self.response({'authentication_token':base64.b64encode(bytes(range(8))).decode(),'challenge-response':'test','authentication_token_expires_in':3600})
                elif endpoint == 'led/mode':
                    if owner.fail:
                        self.response({'code':1001})
                    else:
                        owner.mode = data['mode'];self.response({})
                else:
                    self.response({})
        self.server = ThreadingHTTPServer(('127.0.0.1',0),Handler)
        self.thread = threading.Thread(target=self.server.serve_forever,daemon=True);self.thread.start()
        self.device = open_device(f'127.0.0.1:{self.server.server_port}')
        class UDP:
            def send(self, packet):
                owner.packets.append(bytes(packet))
            def close(self):
                pass
        self.device._udpclient = UDP()

    def tearDown(self):
        Bridge.close_device(self.device)
        self.server.shutdown();self.server.server_close();self.thread.join()

    def frame(self, mode, phase, color):
        self.device.ensure_rt(force=True)
        colors = frame_colors(mode,24,phase,color,[])
        self.device.show_rt_frame([self.device.make_pixel(*rgb) for rgb in colors])
        # Protocol 3: type, 8-byte token, 2 reserved bytes and packet index.
        self.assertEqual(self.packets[-1][0],3)
        return self.packets[-1][12:]

    def test_green_color_uniform_and_chase_after_off(self):
        first = self.frame('chase',0.1,(255,64,128))
        green = self.frame('chase',0.2,(0,255,0))
        self.assertNotEqual(first,green);self.assertEqual(self.mode,'rt')
        self.assertEqual(self.frame('color',0,(0,255,0)),bytes([0,255,0])*24)
        self.device.set_mode('off');self.assertEqual(self.mode,'off')
        a = self.frame('chase',0.2,(0,255,0))
        b = self.frame('chase',0.3,(0,255,0))
        self.assertNotEqual(a,b);self.assertEqual(self.mode,'rt')

    def test_external_mode_change_and_rejected_command(self):
        self.frame('chase',0,(0,255,0))
        self.mode = 'movie'
        self.assertTrue(self.device.ensure_rt())
        self.assertEqual(self.mode,'rt')
        self.fail = True
        with self.assertRaisesRegex(RuntimeError,'1001'):
            self.device.set_mode('off')
        self.assertEqual(self.device.curr_mode,'rt')

    def test_restore_modern_color_mode(self):
        self.device.set_mode('color')
        self.assertEqual(self.mode,'color')


if __name__ == '__main__':
    unittest.main()
