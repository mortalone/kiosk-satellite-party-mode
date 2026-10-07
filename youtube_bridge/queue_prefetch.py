"""Read MA queues and prepare upcoming YouTube audio; never mutate queues."""
import asyncio
import time
from urllib.parse import urlparse

import httpx


def youtube_id(item, bridge):
    media = item.get("media_item") or {}
    candidates = [(media.get("provider", ""), media.get("item_id", ""))]
    for mapping in media.get("provider_mappings") or []:
        if mapping.get("provider_domain") == "opensubsonic":
            candidates.append((mapping.get("provider_instance", ""), mapping.get("item_id", "")))
    uri = urlparse(item.get("uri") or media.get("uri") or "")
    candidates.append((uri.scheme, uri.path.rstrip("/").rsplit("/", 1)[-1]))
    for provider, item_id in candidates:
        if isinstance(provider, str) and isinstance(item_id, str) and provider.startswith("opensubsonic") and bridge.find(item_id):
            return item_id
    return None


class QueuePrefetch:
    def __init__(self, bridge, client=None):
        self.bridge = bridge
        self.enabled = bool(bridge.options.get("prefetch_enabled", False))
        self.url = str(bridge.options.get("music_assistant_url", "")).rstrip("/")
        self.token = str(bridge.options.get("music_assistant_token", ""))
        self.count = min(5, max(1, int(bridge.options.get("prefetch_tracks", 2))))
        parsed = urlparse(self.url)
        self.configured = bool(parsed.scheme in {"http", "https"} and parsed.hostname
                               and not parsed.username and not parsed.password and self.token)
        self.client = client
        self.wanted = []
        self.retry_after = {}
        self.wake = asyncio.Event()
        self.worker = None
        self.status = {"enabled": self.enabled, "configured": self.configured,
                       "state": "disabled" if not self.enabled else "waiting_for_configuration",
                       "last_check": None, "downloading": None}

    async def call(self, command, args=None):
        response = await self.client.post(self.url + "/api", headers={"Authorization": "Bearer " + self.token},
                                          json={"command": command, "args": args or {}}, timeout=10)
        response.raise_for_status()
        result = response.json()
        if isinstance(result, dict) and ("error_code" in result or "error" in result):
            raise ValueError("Music Assistant API rejected the queue request")
        return result

    async def scan(self):
        queues = await self.call("player_queues/all")
        if not isinstance(queues, list):
            raise ValueError("Invalid Music Assistant queue response")
        wanted = []
        for queue in queues:
            if queue.get("available") is False or queue.get("active") is False:
                continue
            if queue.get("state") not in {"playing", "paused"} and not queue.get("active"):
                continue
            index = queue.get("current_index")
            offset = max(0, int(index) + 1) if index is not None else 0
            items = await self.call("player_queues/items", {"queue_id": queue["queue_id"], "offset": offset, "limit": 50})
            per_queue = []
            for item in items:
                key = youtube_id(item, self.bridge)
                if key and key not in per_queue:
                    per_queue.append(key)
                if len(per_queue) >= self.count:
                    break
            wanted.extend(key for key in per_queue if key not in wanted)
            if len(wanted) >= 6:
                break
        self.wanted = wanted[:6]
        await self.bridge.cancel_prefetch(keep=set(self.wanted))
        self.status.update(state="connected", last_check=time.time())
        self.wake.set()

    async def work(self):
        while True:
            await self.wake.wait()
            self.wake.clear()
            for key in list(self.wanted):
                if key not in self.wanted or self.bridge.foreground_audio:
                    continue
                if self.retry_after.get(key, 0) > time.monotonic():
                    continue
                if (self.bridge.cache / (key + ".mp3")).is_file():
                    continue
                self.status["downloading"] = key
                try:
                    await self.bridge.audio(key, prefetch=True)
                except asyncio.CancelledError:
                    # An obsolete or lower-priority download was cancelled, not this worker.
                    if asyncio.current_task().cancelling():
                        raise
                    self.retry_after[key] = time.monotonic() + 10
                except Exception:
                    self.retry_after[key] = time.monotonic() + 300
                finally:
                    self.status["downloading"] = None
            if len(self.retry_after) > 100:
                self.retry_after = {k: v for k, v in self.retry_after.items() if k in self.wanted}

    def snapshot(self):
        return {**self.status, "upcoming": list(self.wanted),
                "cached": [key for key in self.wanted if (self.bridge.cache / (key + ".mp3")).is_file()]}

    async def run(self):
        if not self.enabled or not self.configured:
            return
        own_client = self.client is None
        if own_client:
            self.client = httpx.AsyncClient(trust_env=False, follow_redirects=False)
        self.worker = asyncio.create_task(self.work())
        try:
            while True:
                try:
                    await self.scan()
                except Exception:
                    self.wanted = []
                    await self.bridge.cancel_prefetch(keep=set())
                    self.status["state"] = "connection_error"
                await asyncio.sleep(10)
        finally:
            self.worker.cancel()
            await asyncio.gather(self.worker, return_exceptions=True)
            await self.bridge.cancel_prefetch(keep=set())
            if own_client:
                await self.client.aclose()
