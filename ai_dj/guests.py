"""Queue-scoped guest capabilities for the independent Party web page."""
import secrets
import threading
import time
from urllib.parse import urlsplit


class Guests:
    def __init__(self, dj):
        self.dj = dj
        self.sessions = {}
        self.lock = threading.RLock()

    def link(self, data):
        if not getattr(self.dj, 'guest_allowed', lambda: True)():
            raise ValueError('Gæsteadgang er slået fra af værten')
        queue = self.dj.queue_id()
        if data.get('queue_id') != queue:
            raise ValueError('Vælg samme MA-kø i gæsteserveren og Kiosk Party')
        flags = data.get('modes', {})
        if not isinstance(flags, dict):
            raise ValueError('Ugyldige søgevalg')
        modes = {key: flags.get(key) is True for key in ('library', 'similar', 'ai', 'current_similar')}
        now = time.monotonic()
        with self.lock:
            self.sessions = {k: v for k, v in self.sessions.items() if v['expires'] > now}
            token = next((k for k, v in self.sessions.items() if v['queue'] == queue), None)
            if token is None:
                if len(self.sessions) >= 16:
                    raise ValueError('For mange gæstesessioner')
                token = secrets.token_urlsafe(32)
                self.sessions[token] = {'queue': queue, 'expires': now + 21600, 'jobs': {}, 'last': -1000, 'last_ai': -1000}
            self.sessions[token]['modes'] = modes
        return {'path': '/guest/#token=' + token}

    def session(self, token):
        if not getattr(self.dj, 'guest_allowed', lambda: True)():
            raise ValueError('Gæsteadgang er slået fra af værten')
        with self.lock:
            session = self.sessions.get(token)
            if session is None or session['expires'] <= time.monotonic():
                raise ValueError('Scan QR-koden igen for at åbne gæstesiden')
            if session['queue'] != self.dj.queue_id():
                raise ValueError('Party-køen er ændret. Scan QR-koden igen')
            return session

    def modes(self, session):
        configured = self.dj.search_config()
        return {key: enabled and configured.get(key, True) for key, enabled in session['modes'].items()}

    def config(self, token):
        session = self.session(token)
        queue = self.dj.ma('player_queues/get', {'queue_id': session['queue']})
        current = (queue or {}).get('current_item') or {}
        track = current.get('media_item') or {}
        return {'modes': self.modes(session), 'current': {'name': track.get('name', ''), 'uri': track.get('uri', '')}}

    def search(self, token, data):
        session = self.session(token)
        mode = data.get('mode')
        permission = 'current_similar' if mode == 'track_similar' else mode
        if mode not in ('library', 'similar', 'ai', 'current_similar', 'track_similar') or not self.modes(session).get(permission):
            raise ValueError('Denne søgemåde er slået fra i Home Assistant')
        prompt = data.get('query', '')
        if mode not in ('current_similar', 'track_similar') and (not isinstance(prompt, str) or not 1 <= len(prompt.strip()) <= 1000):
            raise ValueError('Skriv et musikønske eller en titel')
        now = time.monotonic()
        with self.lock:
            key = 'last_ai' if mode == 'ai' else 'last'
            if now - session[key] < (30 if mode == 'ai' else 2):
                raise ValueError('Vent et øjeblik før næste søgning')
            session[key] = now
            session['jobs'] = {k: v for k, v in session['jobs'].items() if now - v['created'] < 1800}
            if len(session['jobs']) >= 32:
                raise ValueError('For mange aktive søgninger; prøv senere')
        if mode == 'ai':
            result = self.dj.suggest({'prompt': prompt, 'count': 8})
        else:
            if mode in ('current_similar', 'track_similar'):
                uri = self.config(token)['current']['uri'] if mode == 'current_similar' else self.reference(token, session, data)
                parsed = urlsplit(uri)
                if not parsed.scheme or parsed.netloc != 'track' or not parsed.path:
                    raise ValueError('Der er ikke et aktuelt nummer at finde lignende musik til')
                tracks = self.dj.ma('music/tracks/similar_tracks', {'item_id': parsed.path.lstrip('/'), 'provider_instance_id_or_domain': parsed.scheme, 'limit': 12, 'allow_lookup': True})
            else:
                args = {'search_query': prompt, 'media_types': ['track'], 'limit': 12}
                if mode == 'similar':
                    args['providers'] = ['sonic_similarity']
                result = self.dj.ma('music/search', args)
                tracks = (result or {}).get('tracks', [])
            result = {'id': secrets.token_urlsafe(16), 'state': 'ready', 'tracks': self.valid_tracks(tracks), 'progress': ''}
        with self.lock:
            session['jobs'][result['id']] = {'created': now, 'added': set(), 'mode': mode, 'result': result if mode != 'ai' else None}
        return {'id': result['id']}

    def reference(self, token, session, data):
        # Accept only a row from this queue or this guest's verified search job.
        if 'queue_item_id' in data:
            item_id = data['queue_item_id']
            if not isinstance(item_id, str) or not item_id:
                raise ValueError('Vælg et nummer i køen')
            queue = self.dj.ma('player_queues/get', {'queue_id': session['queue']})
            items = self.dj.ma('player_queues/items', {'queue_id': session['queue'],
                'offset': max(0, int(queue.get('current_index') or 0) - 1), 'limit': 50}) or []
            track = next(((item.get('media_item') or {}) for item in items if item.get('queue_item_id') == item_id), None)
            if track is None:
                raise ValueError('Nummeret er ikke længere i den viste kø')
        else:
            result = self.job(token, data.get('id'))
            index = data.get('index')
            source_mode = session['jobs'][result['id']]['mode']
            source_permission = 'current_similar' if source_mode == 'track_similar' else source_mode
            if not self.modes(session).get(source_permission) or result['state'] != 'ready' or isinstance(index, bool) or not isinstance(index, int) or not 0 <= index < len(result['tracks']):
                raise ValueError('Vælg et nummer fra dine søgeresultater')
            track = result['tracks'][index]
        return track.get('uri', '')

    @staticmethod
    def valid_tracks(tracks):
        if not isinstance(tracks, list):
            return []
        return [t for t in tracks[:12] if isinstance(t, dict) and t.get('available', True) and isinstance(t.get('uri'), str) and '://' in t['uri']]

    def job(self, token, job_id):
        session = self.session(token)
        with self.lock:
            job = session['jobs'].get(job_id)
            if job is None or time.monotonic() - job['created'] >= 1800:
                raise ValueError('Søgningen er udløbet eller tilhører en anden gæst')
            result = job['result'] or self.dj.job(job_id)
            return {'id': job_id, 'state': result['state'], 'tracks': self.valid_tracks(result.get('tracks', [])), 'progress': result.get('progress', ''), 'error': result.get('error', ''), 'added': sorted(job['added'])}

    def enqueue(self, token, data):
        with self.dj.queue_lock:
            session = self.session(token)
            result = self.job(token, data.get('id'))
            if not self.modes(session).get('current_similar' if session['jobs'][result['id']]['mode'] == 'track_similar' else session['jobs'][result['id']]['mode']):
                raise ValueError('Denne søgemåde er slået fra i Home Assistant')
            indices = data.get('indices')
            if result['state'] != 'ready' or not isinstance(indices, list) or not indices or len(indices) > 12 or len(set(indices)) != len(indices):
                raise ValueError('Vælg numre fra dine søgeresultater')
            if any(isinstance(i, bool) or not isinstance(i, int) or not 0 <= i < len(result['tracks']) or i in result['added'] for i in indices):
                raise ValueError('Numrene er ugyldige eller allerede tilføjet')
            uris = [result['tracks'][i]['uri'] for i in indices]
            if hasattr(self.dj, 'guest_queue'):
                self.dj.guest_queue(session['queue'], uris)
            else:
                self.dj.ma('player_queues/play_media', {'queue_id': session['queue'], 'media': uris, 'option': 'add'})
            with self.lock:
                session['jobs'][result['id']]['added'].update(indices)
            return {'queued': len(indices)}
