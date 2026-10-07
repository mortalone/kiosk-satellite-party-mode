import sys
import threading
import unittest
from pathlib import Path
from unittest.mock import Mock, patch
from http.server import ThreadingHTTPServer
import requests
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from server import Portal, handler


class PortalTest(unittest.TestCase):
    def setUp(self):
        self.portal = Portal({'queue_id': 'group', 'api_token': 'host-secret-' * 4, 'public_url': 'http://ha:8102'})
        self.track = {'uri': 'library://track/7', 'name': 'Jazz', 'artists': [{'name': 'Artist'}]}
        self.portal.ma = Mock(return_value={'tracks': [self.track]})
        self.token = self.portal.join()['path'].split('=')[1]

    def test_search_and_append_without_ai_installed(self):
        with patch('requests.request', side_effect=AssertionError('AI must not be contacted')):
            modes = self.portal.search_config()
            self.assertTrue(modes['library']); self.assertTrue(modes['similar']); self.assertFalse(modes['ai'])
            result = self.portal.guests.search(self.token, {'mode': 'library', 'query': 'Jazz'})
            self.portal.guests.enqueue(self.token, {'id': result['id'], 'indices': [0], 'option': 'replace', 'queue_id': 'other'})
            self.portal.ma.assert_called_with('player_queues/play_media', {'queue_id': 'group', 'media': ['library://track/7'], 'option': 'add'})
            with self.assertRaises(ValueError):
                self.portal.guests.search(self.token, {'mode': 'ai', 'query': 'Jazz'})

    def test_direct_join_preserves_host_disabled_modes_and_queue_changes(self):
        self.portal.guests.link({'queue_id': 'group', 'modes': {'library': False, 'similar': True}})
        self.assertEqual(self.portal.join()['path'].split('=')[1], self.token)
        self.assertFalse(self.portal.guests.modes(self.portal.guests.session(self.token))['library'])
        self.portal.options['queue_id'] = 'other'
        with self.assertRaises(ValueError): self.portal.guests.session(self.token)
        self.assertNotEqual(self.portal.join()['path'].split('=')[1], self.token)

    def test_guest_access_off_revokes_sessions_and_ha_unavailable_is_closed(self):
        self.portal.options['guest_access'] = False
        with self.assertRaises(ValueError): self.portal.join()
        with self.assertRaises(ValueError): self.portal.guests.session(self.token)
        self.portal.options.update(guest_access=True, guest_access_entity='switch.guest')
        self.portal.ha_get = Mock(side_effect=requests.ConnectionError())
        with self.assertRaises(ValueError): self.portal.guests.session(self.token)
        self.portal.options.pop('guest_access_entity')
        self.portal.options['search_library_entity'] = 'switch.library'
        self.assertFalse(self.portal.search_config()['library'])

    def test_optional_ai_unavailable_keeps_search_enabled(self):
        self.portal.options.update(ai_dj_url='http://dj:8101', ai_dj_token='remote-secret-' * 3)
        self.portal.ai_request = Mock(side_effect=requests.ConnectionError())
        modes = self.portal.search_config()
        self.assertFalse(modes['ai']); self.assertTrue(modes['library']); self.assertTrue(modes['similar'])
        self.portal.ai_cached = (0, False)
        self.portal.ai_request = Mock(return_value={'ai': True})
        self.assertTrue(self.portal.search_config()['ai'])
        self.portal.ai_request = Mock(side_effect=[{'id': 'remote-job'}, {'state': 'ready', 'tracks': [self.track]}])
        result = self.portal.guests.search(self.token, {'mode': 'ai', 'query': 'rolig jazz'})
        self.assertEqual(self.portal.guests.job(self.token, result['id'])['tracks'], [self.track])
        with self.assertRaises(ValueError): self.portal.guests.job(self.token, 'other-remote-job')

    def test_actual_remote_ai_api_never_receives_guest_queue_actions(self):
        self.portal.options.update(ai_dj_url='http://dj:8101', ai_dj_token='remote-secret-' * 3)
        response = Mock(); response.json.return_value = {'id': 'remote-job'}
        with patch('requests.request', return_value=response) as request:
            self.portal.suggest({'prompt': 'Jazz', 'count': 8})
            request.assert_called_once_with('POST', 'http://dj:8101/api/suggest', headers={'Authorization': 'Bearer ' + self.portal.options['ai_dj_token']}, json={'prompt': 'Jazz', 'count': 8}, timeout=(2, 5))
        with self.assertRaises(ValueError): self.portal.job('../admin/ai')

    def test_direct_http_url_and_host_isolation(self):
        server = ThreadingHTTPServer(('127.0.0.1', 0), handler(self.portal))
        threading.Thread(target=server.serve_forever, daemon=True).start()
        self.addCleanup(server.server_close); self.addCleanup(server.shutdown)
        base = 'http://127.0.0.1:' + str(server.server_port)
        page = requests.get(base + '/guest/')
        self.assertEqual(page.status_code, 200); self.assertIn('const standalone=true;', page.text)
        link = requests.get(base + '/api/guest/join')
        self.assertEqual(link.status_code, 200); self.assertNotIn('host-secret', link.text)
        headers = {'Authorization': 'Bearer ' + link.json()['path'].split('=')[1]}
        self.portal.ma.return_value = {'current_item': {'media_item': self.track}}
        self.assertEqual(requests.get(base + '/api/guest/config', headers=headers).status_code, 200)
        for path in ['/api/admin/status', '/api/search-config', '/api/jobs/other']:
            self.assertEqual(requests.get(base + path, headers=headers).status_code, 403)
        for path in ['/api/guest-link', '/api/queue', '/api/suggest']:
            self.assertEqual(requests.post(base + path, headers=headers, json={}).status_code, 403)
        host = {'Authorization': 'Bearer ' + self.portal.options['api_token']}
        status = requests.get(base + '/api/admin/status', headers=host).json()
        self.assertEqual(status['guest_url'], 'http://ha:8102/guest/')
        self.assertNotIn('host-secret', status['guest_url'])
        self.assertIn('host-secret', status['kiosk_url'])
        self.portal.options['guest_access'] = False
        self.assertEqual(requests.get(base + '/api/guest/join').status_code, 400)
        self.assertEqual(requests.get(base + '/api/guest/config', headers=headers).status_code, 400)

    def test_no_ai_import_or_model_requirement_and_shared_capabilities(self):
        root = Path(__file__).resolve().parents[2]
        self.assertNotIn('from dj import', (root / 'party_guest/server.py').read_text())
        self.assertEqual((root / 'party_guest/guests.py').read_bytes(), (root / 'ai_dj/guests.py').read_bytes())
        self.assertEqual((root / 'party_guest/guest.html').read_bytes(), (root / 'ai_dj/guest.html').read_bytes())


if __name__ == '__main__': unittest.main()
