"""Opt-in, bounded feature trace; never stores audio or credentials."""
import copy
import threading
import time
from datetime import datetime, timezone


class Diagnostic:
    def __init__(self, limit=12000, clock=time.monotonic):
        self.lock = threading.Lock()
        self.clock, self.limit = clock, limit
        self.started = None
        self.deadline = 0
        self.active = False
        self.events = []
        self.metadata = {}
        self.truncated = False

    def start(self, metadata):
        with self.lock:
            self.started = self.clock()
            self.deadline = self.started + 60
            self.active = True
            self.events = []
            self.truncated = False
            self.metadata = copy.deepcopy(metadata)
            self.metadata['started_utc'] = datetime.now(timezone.utc).isoformat()

    def stop(self):
        with self.lock:
            self.active = False

    def add(self, kind, **values):
        # No audio processing, serialization or disk I/O in the receiving loop.
        if not self.active:
            return
        with self.lock:
            now = self.clock()
            if not self.active:
                return
            if now >= self.deadline or len(self.events) >= self.limit:
                self.truncated = len(self.events) >= self.limit
                self.active = False
                return
            self.events.append(dict(t_ms=round((now-self.started)*1000, 3), kind=kind, **values))

    def status(self):
        with self.lock:
            if self.active and self.clock() >= self.deadline:
                self.active = False
            return dict(active=self.active, events=len(self.events), available=self.started is not None,
                        remaining_s=max(0, round(self.deadline-self.clock())) if self.active else 0,
                        truncated=self.truncated)

    def export(self):
        self.status()
        with self.lock:
            return dict(schema=1, metadata=copy.deepcopy(self.metadata),
                        active=self.active, truncated=self.truncated,
                        note='Feature/timing trace only. LED send completion is not measured light output. No physical speaker delay is measured.',
                        events=list(self.events))
