import json
import sys
import threading
import time
import unittest
from http.server import ThreadingHTTPServer
from pathlib import Path
from unittest.mock import Mock
import requests

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from dj import DJ, handler


class GuestTest(unittest.TestCase):
    def setUp(self):
        self.dj = DJ({'queue_id': 'group', 'api_token': 'host-secret-' * 4})
        self.addCleanup(self.dj.worker.shutdown)
        self.track = {'uri': 'library://track/7', 'name': 'Jazz', 'artists': [{'name': 'Artist'}]}
        self.dj.ma = Mock(return_value={'tracks': [self.track]})
        self.token = self.link()['path'].split('=')[1]

    def link(self, **modes):
        return self.dj.guests.link({'queue_id': 'group', 'modes': {'library': True, 'similar': True, 'ai': True, 'current_similar': True, **modes}})

    def test_resolved_only_append_no_guest_replacement_or_other_queue(self):
        result = self.dj.guests.search(self.token, {'mode': 'library', 'query': 'jazz'})
        self.dj.guests.enqueue(self.token, {'id': result['id'], 'indices': [0], 'option': 'replace', 'queue_id': 'other', 'media': ['spotify://track/injected']})
        self.dj.ma.assert_called_with('player_queues/play_media', {'queue_id': 'group', 'media': ['library://track/7'], 'option': 'add'})
        with self.assertRaises(ValueError):
            self.dj.guests.enqueue(self.token, {'id': result['id'], 'indices': [0]})
        with self.assertRaises(ValueError):
            self.dj.guests.job(self.token, 'other-host-job')

    def test_queue_change_expiry_and_disabled_mode(self):
        job = self.dj.guests.search(self.token, {'mode': 'library', 'query': 'Jazz'})
        self.link(library=False)
        with self.assertRaises(ValueError):
            self.dj.guests.enqueue(self.token, {'id': job['id'], 'indices': [0]})
        with self.assertRaises(ValueError):
            self.dj.guests.search(self.token, {'mode': 'library', 'query': 'Jazz'})
        self.dj.options['queue_id'] = 'other'
        with self.assertRaises(ValueError):
            self.dj.guests.job(self.token, job['id'])
        self.dj.options['queue_id'] = 'group'
        self.dj.guests.sessions[self.token]['expires'] = time.monotonic() - 1
        with self.assertRaises(ValueError):
            self.dj.guests.session(self.token)
        self.assertNotEqual(self.link()['path'].split('=')[1], self.token)

    def test_ha_switch_disables_guest_even_with_cached_qr(self):
        self.dj.search_config = Mock(return_value={'library': False, 'similar': False, 'ai': False})
        with self.assertRaises(ValueError):
            self.dj.guests.search(self.token, {'mode': 'ai', 'query': 'jazz'})
        self.dj.ma.assert_not_called()

    def test_similar_current_uses_verified_ma_current_uri(self):
        self.dj.ma.side_effect = [{'current_item': {'media_item': self.track}}, [self.track]]
        result = self.dj.guests.search(self.token, {'mode': 'current_similar', 'uri': 'spotify://track/injected'})
        self.dj.ma.assert_called_with('music/tracks/similar_tracks', {'item_id': '7', 'provider_instance_id_or_domain': 'library', 'limit': 12, 'allow_lookup': True})
        self.assertEqual(self.dj.guests.job(self.token, result['id'])['tracks'], [self.track])

    def test_similar_text_and_ai_job_restrictions(self):
        self.dj.guests.search(self.token, {'mode': 'similar', 'query': 'calm jazz'})
        self.dj.ma.assert_called_with('music/search', {'search_query': 'calm jazz', 'media_types': ['track'], 'limit': 12, 'providers': ['sonic_similarity']})
        self.dj.suggest = Mock(return_value={'id': 'ai-guest-job'})
        self.dj.job = Mock(return_value={'state': 'ready', 'tracks': [self.track]})
        result = self.dj.guests.search(self.token, {'mode': 'ai', 'query': 'roligt jazz musik'})
        self.assertEqual(self.dj.guests.job(self.token, result['id'])['tracks'], [self.track])
        with self.assertRaises(ValueError):
            self.dj.guests.search(self.token, {'mode': 'ai', 'query': 'jazz'})
        with self.assertRaises(ValueError):
            self.dj.guests.link({'queue_id': 'other', 'modes': {}})

    def test_http_guest_cannot_call_host_endpoints(self):
        server = ThreadingHTTPServer(('127.0.0.1', 0), handler(self.dj))
        thread = threading.Thread(target=server.serve_forever, daemon=True); thread.start()
        self.addCleanup(server.server_close); self.addCleanup(server.shutdown)
        base = 'http://127.0.0.1:' + str(server.server_port)
        headers = {'Authorization': 'Bearer ' + self.token}
        self.assertEqual(requests.get(base + '/guest/').status_code, 200)
        self.assertEqual(requests.get(base + '/api/guest/config').status_code, 401)
        for endpoint in ['/api/admin/ai', '/api/search-config', '/api/jobs/host']:
            self.assertEqual(requests.get(base + endpoint, headers=headers).status_code, 403)
        for endpoint in ['/api/guest-link', '/api/queue', '/api/suggest']:
            self.assertEqual(requests.post(base + endpoint, headers=headers, json={}).status_code, 403)
        master = {'Authorization': 'Bearer ' + self.dj.options['api_token']}
        response = requests.post(base + '/api/guest-link', headers=master, json={'queue_id': 'group', 'modes': {'library': True}})
        self.assertEqual(response.status_code, 200)
        self.assertNotIn(self.dj.options['api_token'], response.text)
        self.assertEqual(requests.post(base + '/api/guest/search', headers=headers, json={'mode': 'library', 'query': 'Jazz'}).status_code, 202)


if __name__ == '__main__':
    unittest.main()
