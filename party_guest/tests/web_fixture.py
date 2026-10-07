"""Local fake MA for browser checks; never included in the add-on image."""
import sys
import threading
from http.server import ThreadingHTTPServer
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from server import Portal, handler

class FixturePortal(Portal):
    def __init__(self):
        super().__init__({'queue_id': 'group', 'api_token': 'browser-fixture-host-secret-123', 'public_url': 'http://127.0.0.1:18102'})
        self.added = []
        self.tracks = [{'uri': 'library://track/1', 'name': 'Aftenlys', 'artists': [{'name': 'Natteholdet'}]},
                       {'uri': 'library://track/2', 'name': 'Stjernestøv', 'artists': [{'name': 'Natteholdet'}]}]
    def ma(self, command, args):
        if command == 'player_queues/get': return {'state': 'playing', 'current_index': 0, 'items': 2, 'current_item': {'queue_item_id': 'q0', 'media_item': self.tracks[0]}}
        if command == 'player_queues/items': return [{'queue_item_id': 'q'+str(i), 'media_item': t} for i,t in enumerate(self.tracks)]
        if command == 'music/search': return {'tracks': self.tracks}
        if command == 'music/tracks/similar_tracks': return self.tracks
        if command == 'player_queues/play_media':
            assert args['queue_id'] == 'group' and args['option'] == self.policy()['queue_option']
            assert set(args['media']).issubset({t['uri'] for t in self.tracks})
            self.added.extend(args['media']); return None
        raise AssertionError(command)
    def ai_available(self): return self.party_policy['auto_method'] == 'ai'
    def suggest(self, data): return {'id': 'fixture-ai-job'}
    def job(self, key): return {'state': 'ready', 'tracks': self.tracks}
    def ai_request(self, path, data=None):
        raise AssertionError('No AI service exists in this fixture')

portal = FixturePortal()
class TrustedIngress(handler(portal, True)):
    def setup(self):
        super().setup()
        self.client_address = ('172.30.32.2', self.client_address[1])

ingress = ThreadingHTTPServer(('127.0.0.1', 18103), TrustedIngress)
threading.Thread(target=ingress.serve_forever, daemon=True).start()
ThreadingHTTPServer(('127.0.0.1', 18102), handler(portal)).serve_forever()
