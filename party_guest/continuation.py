"""Party queue filler. Only add a bounded tail; never start/replace a player."""
import random
import threading
import time
from collections import deque
from urllib.parse import urlsplit

METHODS = {'favorites', 'similar', 'ai'}
PLACEMENTS = {'add', 'next', 'play', 'replace_next'}
PLACEMENT_TEXT = {
    'add': 'Dit musikønske tilføjes sidst i køen. Det aktuelle nummer fortsætter.',
    'next': 'Dit musikønske lægges som næste i køen. Det aktuelle nummer fortsætter.',
    'play': 'Dit musikønske afspilles med det samme. Resten af køen bevares.',
    'replace_next': 'Dit musikønske erstatter de kommende numre. Det aktuelle nummer fortsætter.',
}


class Continuation:
    def __init__(self, portal):
        self.portal = portal
        self.lock = threading.RLock()
        self.wake = threading.Event()
        self.epoch = 0
        self.pending = None
        self.after = 0
        self.history = deque(maxlen=200)
        self.recent = deque(maxlen=160)
        self.info = {'status': 'Automatisk fortsættelse er slået fra', 'added': 0, 'remaining': 0}

    def changed(self):
        with self.lock:
            self.epoch += 1
            self.pending = None
            self.after = 0
        self.wake.set()

    def guest_added(self):
        # Cancel a result generated before guests selected new music.
        self.changed()

    def status(self):
        with self.lock:
            return dict(self.info)

    @staticmethod
    def remaining(queue):
        index = queue.get('current_index')
        return max(0, int(queue.get('items', 0)) - (int(index) + 1 if index is not None else 0))

    def snapshot(self, queue_id, queue):
        return self.portal.ma('player_queues/items', {'queue_id': queue_id,
            'offset': max(0, int(queue.get('current_index') or 0)), 'limit': 128}) or []

    def tick(self, now=None):
        now = time.monotonic() if now is None else now
        policy = self.portal.policy()
        with self.lock:
            if not policy['continuous']:
                self.pending = None
                self.info['status'] = 'Automatisk fortsættelse er slået fra'
                return
            if now < self.after:
                return
            epoch, pending = self.epoch, self.pending
        try:
            queue_id = self.portal.queue_id()
            queue = self.portal.ma('player_queues/get', {'queue_id': queue_id})
            if queue.get('state') != 'playing':
                with self.lock:
                    self.info['status'] = 'Venter · afspilleren er pauset eller stoppet'
                return
            remaining = self.remaining(queue)
            with self.lock:
                self.info['remaining'] = remaining
            target = policy['auto_count']
            if remaining > target:
                with self.lock:
                    self.pending = None
                    self.info['status'] = f'Gæsternes kø spiller · {remaining} kommende numre'
                return
            items = self.snapshot(queue_id, queue)
            existing = {(item.get('media_item') or {}).get('uri') for item in items}
            current = (queue.get('current_item') or {}).get('media_item') or {}
            method = policy['auto_method']
            if pending is not None and (pending['queue'] != queue_id or pending['policy'] != policy or
                    any(item.get('queue_item_id') not in pending['ids'] for item in items)):
                with self.lock:
                    self.pending = None
                pending = None
            if pending is None:
                if method == 'ai':
                    if not self.portal.ai_available():
                        raise ValueError('AI DJ er ikke tilsluttet; vælg Favoritter eller Samme stil')
                    if not policy['auto_prompt']:
                        raise ValueError('Angiv et AI-musikønske i Party Guest ingress')
                    excluded = list(self.recent) + [self.exclusion(item.get('media_item') or {}) for item in items[:40]]
                    result = self.portal.suggest({'prompt': policy['auto_prompt'], 'count': max(3, target), 'exclude': excluded})
                    pending = {'id': result['id'], 'tracks': None}
                elif method == 'favorites':
                    tracks = self.portal.ma('music/tracks/library_items', {'favorite': True, 'limit': 200, 'order_by': 'random'})
                    random.shuffle(tracks)
                    pending = {'tracks': tracks}
                else:
                    uri = urlsplit(current.get('uri', ''))
                    if not uri.scheme or uri.netloc != 'track' or not uri.path:
                        raise ValueError('Der mangler et aktuelt nummer at finde lignende musik til')
                    tracks = self.portal.ma('music/tracks/similar_tracks', {'item_id': uri.path.lstrip('/'),
                        'provider_instance_id_or_domain': uri.scheme, 'limit': 25, 'allow_lookup': True})
                    pending = {'tracks': tracks}
                pending.update(queue=queue_id, policy=policy, ids={item.get('queue_item_id') for item in items})
                with self.lock:
                    if epoch != self.epoch:
                        return
                    self.pending = pending
            if pending['tracks'] is None:
                job = self.portal.job(pending['id'])
                if job['state'] == 'working':
                    with self.lock:
                        self.info['status'] = 'AI forbereder næste nummer…'
                    return
                if job['state'] != 'ready':
                    raise ValueError(job.get('error') or 'AI kunne ikke finde næste nummer')
                pending['tracks'] = job['tracks']
            # Keep precomputed candidates ready, but do not add while the target is full.
            if remaining >= target:
                return
            valid = self.valid_candidates(pending['tracks'])
            candidates = [track for track in valid
                          if track['uri'] not in existing and track['uri'] not in self.history]
            # A provider may return a finite pool: cycle once eligible candidates played.
            if not candidates and method in {'favorites', 'similar'}:
                candidates = [track for track in valid if track['uri'] not in existing]
                if candidates:
                    self.history.clear()
            seen = set()
            candidates = [track for track in candidates if not (track['uri'] in seen or seen.add(track['uri']))]
            if not candidates:
                raise ValueError('Ingen nye numre uden gentagelser; prøver igen om et minut')
            with self.portal.queue_lock, self.lock:
                if epoch != self.epoch or self.portal.policy() != policy or self.portal.queue_id() != queue_id:
                    return
                latest = self.portal.ma('player_queues/get', {'queue_id': queue_id})
                if latest.get('state') != 'playing':
                    return
                latest_items = self.snapshot(queue_id, latest)
                if any(item.get('queue_item_id') not in pending['ids'] for item in latest_items):
                    self.pending = None
                    return
                room = max(0, target - self.remaining(latest))
                if not room:
                    return
                uris = [track['uri'] for track in candidates[:room]]
                self.portal.ma('player_queues/play_media', {'queue_id': queue_id, 'media': uris, 'option': 'add'})
                self.history.extend(uris)
                self.recent.extend(self.exclusion(track) for track in candidates[:room])
                self.info['added'] += len(uris)
                self.info['status'] = f'Tilføjede {len(uris)} automatisk · nye ønsker kan tilføjes'
                self.pending = None
                self.after = now + 10
        except Exception as error:
            with self.lock:
                if epoch == self.epoch:
                    self.pending = None
                    self.after = now + 60
                    self.info['status'] = str(error)[:220]

    def valid_candidates(self, tracks):
        if not isinstance(tracks, list):
            return []
        return [track for offset in range(0, min(len(tracks), 200), 12)
                for track in self.portal.guests.valid_tracks(tracks[offset:offset+12])]

    @staticmethod
    def exclusion(track):
        return {'uri': track.get('uri', ''), 'title': track.get('name', ''),
                'artist': ', '.join(a.get('name', '') for a in track.get('artists', []))}

    def run(self):
        while True:
            self.wake.wait(5)
            self.wake.clear()
            self.tick()

    def start_worker(self):
        threading.Thread(target=self.run, daemon=True).start()
