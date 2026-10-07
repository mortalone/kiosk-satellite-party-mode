"""Independent Party guest portal. AI DJ is an optional remote search engine."""
import hmac
import json
import os
import re
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlsplit
import requests
from guests import Guests


class Portal:
    def __init__(self, options):
        self.options = dict(options)
        self.queue_lock = threading.Lock()
        self.guests = Guests(self)
        self.ai_cached = (0, False)

    def ha_get(self, path):
        response = requests.get('http://supervisor/core/api/' + path,
            headers={'Authorization': 'Bearer ' + os.environ.get('SUPERVISOR_TOKEN', '')}, timeout=(3, 10))
        response.raise_for_status()
        return response.json()

    def enabled(self, option, default=True):
        entity = self.options.get(option, '')
        if not entity:
            return default
        if not isinstance(entity, str) or not re.fullmatch(r'(switch|input_boolean)\.[a-z0-9_]+', entity):
            return False
        try:
            return self.ha_get('states/' + entity).get('state') == 'on'
        except (requests.RequestException, ValueError, TypeError):
            return False

    def queue_id(self):
        if not self.options.get('guest_access', True) or not self.enabled('guest_access_entity'):
            raise ValueError('Gæsteadgang er slået fra af værten')
        queue = self.options.get('queue_id', '').strip()
        if not queue:
            raise ValueError('Angiv queue_id eller MA-gruppens HA media_player i Party Guest')
        if queue.startswith('media_player.'):
            if not re.fullmatch(r'media_player\.[a-z0-9_]+', queue):
                raise ValueError('Ugyldigt media_player-id')
            queue = self.ha_get('states/' + queue).get('attributes', {}).get('active_queue')
            if not isinstance(queue, str) or not queue:
                raise ValueError('Den valgte MA-afspiller har ingen active_queue')
        return queue

    def ma(self, command, args):
        base = self.options.get('music_assistant_url', '').rstrip('/')
        if urlsplit(base).scheme not in {'http', 'https'}:
            raise ValueError('Angiv Music Assistant-adressen i Party Guest')
        response = requests.post(base + '/api', headers={'Authorization': 'Bearer ' + self.options.get('music_assistant_token', '')},
            json={'command': command, 'args': args}, timeout=(3, 20))
        response.raise_for_status()
        result = response.json()
        if isinstance(result, dict) and ('error' in result or 'error_code' in result):
            raise ValueError(str(result.get('details') or result.get('error') or 'MA afviste kaldet')[:200])
        return result

    def ai_request(self, path, data=None):
        base = self.options.get('ai_dj_url', '').rstrip('/')
        token = self.options.get('ai_dj_token', '')
        parsed = urlsplit(base)
        if parsed.scheme not in {'http', 'https'} or not parsed.hostname or parsed.username or parsed.query or parsed.fragment or len(token) < 24:
            raise ValueError('AI DJ er ikke tilsluttet. Søg og Similar kan bruges uden AI DJ')
        response = requests.request('POST' if data is not None else 'GET', base + path,
            headers={'Authorization': 'Bearer ' + token}, json=data, timeout=(2, 5))
        response.raise_for_status()
        result = response.json()
        if isinstance(result, dict) and result.get('error'):
            raise ValueError(str(result['error'])[:200])
        return result

    def ai_available(self):
        now = time.monotonic()
        if now - self.ai_cached[0] < 5:
            return self.ai_cached[1]
        available = False
        if self.options.get('ai_dj_url') and len(self.options.get('ai_dj_token', '')) >= 24:
            try:
                available = self.ai_request('/api/search-config').get('ai') is True
            except (requests.RequestException, ValueError, TypeError):
                pass
        self.ai_cached = (now, available)
        return available

    def search_config(self):
        modes = {key: self.enabled('search_' + key + '_entity') for key in ('library', 'similar', 'ai', 'current_similar')}
        modes['ai'] = modes['ai'] and self.ai_available()
        return modes

    def suggest(self, data):
        return self.ai_request('/api/suggest', data)

    def job(self, key):
        if not isinstance(key, str) or not re.fullmatch(r'[A-Za-z0-9_-]{1,100}', key):
            raise ValueError('Ugyldigt AI-søge-id')
        return self.ai_request('/api/jobs/' + key)

    def join(self):
        queue = self.queue_id()
        with self.guests.lock:
            token = next((key for key, value in self.guests.sessions.items()
                          if value['queue'] == queue and value['expires'] > time.monotonic()), None)
            if token:
                return {'path': '/guest/#token=' + token}
            return self.guests.link({'queue_id': queue, 'modes': {key: True for key in ('library', 'similar', 'ai', 'current_similar')}})

    def status(self):
        public = urlsplit(self.options.get('public_url', ''))
        url = ''
        if public.scheme in {'http', 'https'} and public.hostname and not public.username and not public.query and not public.fragment:
            url = public.scheme + '://' + public.netloc + '/guest/'
        kiosk = urlsplit(url)
        master = self.options.get('api_token', '')
        kiosk_url = kiosk.scheme + '://' + kiosk.netloc + '/#token=' + master if url and len(master) >= 24 else ''
        return {'guest_url': url, 'kiosk_url': kiosk_url, 'modes': self.search_config(), 'guest_access': bool(self.options.get('guest_access', True)) and self.enabled('guest_access_entity')}


def handler(portal, ingress=False):
    class Handler(BaseHTTPRequestHandler):
        def setup(self):
            super().setup()
            self.connection.settimeout(10)
        def log_message(self, *args):
            pass
        def do_GET(self):
            self.handle_request(False)
        def do_POST(self):
            self.handle_request(True)
        def reply(self, status, data):
            body = json.dumps(data, ensure_ascii=False).encode()
            self.send_response(status)
            self.send_header('Content-Type', 'application/json')
            self.send_header('Cache-Control', 'no-store')
            self.send_header('Content-Length', str(len(body)))
            self.end_headers()
            self.wfile.write(body)
        def page(self, name):
            body = Path(__file__).with_name(name).read_bytes()
            if name == 'guest.html':
                body = body.replace(b'const standalone=false;', b'const standalone=true;')
            self.send_response(200)
            self.send_header('Content-Type', 'text/html; charset=utf-8')
            self.send_header('Cache-Control', 'no-store')
            self.send_header('Referrer-Policy', 'no-referrer')
            self.send_header('Content-Length', str(len(body)))
            self.end_headers()
            self.wfile.write(body)
        def handle_request(self, post):
            path = urlsplit(self.path).path
            if not post and path == '/health':
                return self.reply(200, {'ok': True})
            token = self.headers.get('Authorization', '').removeprefix('Bearer ')
            master = portal.options.get('api_token', '')
            host = self.client_address[0] == '172.30.32.2' if ingress else len(master) >= 24 and hmac.compare_digest(master, token)
            if ingress and not host:
                return self.reply(403, {'error': 'Åbn opsætningen via Home Assistant ingress'})
            if not post and path in {'/', '/index.html'}:
                return self.page('index.html' if ingress else 'guest.html')
            if not post and path in {'/guest', '/guest/', '/guest/index.html'}:
                return self.page('guest.html')
            try:
                # Joining is intentionally public on the mapped guest port. It grants only
                # queue-scoped guest search/append, never host or MA credentials.
                if not ingress and not post and path == '/api/guest/join':
                    return self.reply(200, portal.join())
                if not post and path == '/api/admin/status' and host:
                    return self.reply(200, portal.status())
                if post and path == '/api/guest-link' and host:
                    return self.reply(200, portal.guests.link(self.body()))
                if ingress or path.startswith('/api/admin/') or not path.startswith('/api/guest/'):
                    return self.reply(403, {'error': 'Kun gæstefunktioner er tilgængelige'})
                portal.guests.session(token)
                if not post and path == '/api/guest/config':
                    return self.reply(200, portal.guests.config(token))
                if not post and path.startswith('/api/guest/jobs/'):
                    return self.reply(200, portal.guests.job(token, path.rsplit('/', 1)[1]))
                if post and path == '/api/guest/search':
                    return self.reply(202, portal.guests.search(token, self.body()))
                if post and path == '/api/guest/queue':
                    return self.reply(200, portal.guests.enqueue(token, self.body()))
                self.reply(404, {'error': 'Ukendt endpoint'})
            except Exception as error:
                self.reply(400, {'error': str(error)[:250]})
        def body(self):
            size = int(self.headers.get('Content-Length', '0'))
            if not 1 <= size <= 8192:
                raise ValueError('Ugyldig forespørgsel')
            data = json.loads(self.rfile.read(size))
            if not isinstance(data, dict):
                raise ValueError('Forventede et JSON-objekt')
            return data
    return Handler


if __name__ == '__main__':
    portal = Portal(json.loads(Path('/data/options.json').read_text()))
    api = ThreadingHTTPServer(('0.0.0.0', 8102), handler(portal))
    threading.Thread(target=api.serve_forever, daemon=True).start()
    ThreadingHTTPServer(('0.0.0.0', 8099), handler(portal, True)).serve_forever()
