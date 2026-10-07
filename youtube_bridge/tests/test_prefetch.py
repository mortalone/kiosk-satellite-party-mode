import asyncio
import json
import sys
import tempfile
import unittest
from pathlib import Path

import httpx

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from bridge import Bridge
from queue_prefetch import QueuePrefetch, youtube_id

A, B = "3VaZ-4AG-f0", "dQw4w9WgXcQ"


def queue_item(key, provider="opensubsonic--test"):
    return {"media_item": {"item_id": key, "provider": provider}, "uri": provider + "://track/" + key}


class PrefetchTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.bridge = Bridge({"password": "test-password", "prefetch_enabled": True,
                              "music_assistant_url": "http://ma:8095", "music_assistant_token": "test-token"}, Path(self.temp.name))
        for key in (A, B):
            self.bridge.put({"id": key, "title": key, "duration": 60, "uploader": "Fixture"})

    async def asyncTearDown(self):
        tasks = list(self.bridge.audio_tasks.values())
        for task in tasks:
            task.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)
        self.bridge.db.close()
        self.temp.cleanup()

    async def test_queue_api_filters_sources_and_reads_after_current(self):
        calls = []
        def handle(request):
            self.assertEqual(request.headers["authorization"], "Bearer test-token")
            body = json.loads(request.content)
            calls.append(body)
            if body["command"] == "player_queues/all":
                return httpx.Response(200, json=[{"queue_id": "room", "state": "playing", "active": True, "current_index": 4},
                                                {"queue_id": "offline", "state": "playing", "available": False}])
            self.assertEqual(body["args"], {"queue_id": "room", "offset": 5, "limit": 50})
            return httpx.Response(200, json=[queue_item(A, "spotify"), queue_item(A), queue_item(A), queue_item(B)])
        async with httpx.AsyncClient(transport=httpx.MockTransport(handle)) as client:
            watcher = QueuePrefetch(self.bridge, client)
            await watcher.scan()
            self.assertEqual(watcher.wanted, [A, B])
            self.assertEqual(watcher.snapshot()["state"], "connected")
        self.assertEqual([c["command"] for c in calls], ["player_queues/all", "player_queues/items"])

    async def test_library_mapping_uri_and_unknown_id(self):
        item = {"media_item": {"provider": "library", "item_id": "123", "provider_mappings": [
            {"provider_domain": "opensubsonic", "provider_instance": "opensubsonic--test", "item_id": A}]}}
        self.assertEqual(youtube_id(item, self.bridge), A)
        self.assertEqual(youtube_id({"uri": "opensubsonic--test://track/" + B}, self.bridge), B)
        self.assertIsNone(youtube_id(queue_item("abcdefghijk"), self.bridge))
        self.assertIsNone(youtube_id(queue_item(A, "spotify"), self.bridge))

    async def test_foreground_cancels_different_background_track(self):
        started = asyncio.Event()
        cancelled = []
        async def generate(key):
            if key == A:
                started.set()
                try:
                    await asyncio.Event().wait()
                except asyncio.CancelledError:
                    cancelled.append(key)
                    raise
            path = self.bridge.cache / (key + ".mp3")
            path.write_bytes(b"fixture")
            return path
        self.bridge._generate = generate
        preload = asyncio.create_task(self.bridge.audio(A, prefetch=True))
        await started.wait()
        path = await asyncio.wait_for(self.bridge.audio(B), 1)
        await asyncio.gather(preload, return_exceptions=True)
        self.assertEqual(cancelled, [A])
        self.assertTrue(path.is_file())
        self.assertEqual(self.bridge.foreground_audio, {})

    async def test_cached_playback_does_not_interrupt_prefetch(self):
        started = asyncio.Event()
        async def generate(key):
            started.set()
            await asyncio.Event().wait()
        self.bridge._generate = generate
        (self.bridge.cache / (B + ".mp3")).write_bytes(b"fixture")
        preload = asyncio.create_task(self.bridge.audio(A, prefetch=True))
        await started.wait()
        self.assertTrue((await self.bridge.audio(B)).is_file())
        self.assertFalse(preload.done())
        await self.bridge.cancel_prefetch(keep=set())
        await asyncio.gather(preload, return_exceptions=True)

    async def test_same_track_promotes_existing_download(self):
        started, finish = asyncio.Event(), asyncio.Event()
        calls = []
        async def generate(key):
            calls.append(key)
            started.set()
            await finish.wait()
            path = self.bridge.cache / (key + ".mp3")
            path.write_bytes(b"fixture")
            return path
        self.bridge._generate = generate
        preload = asyncio.create_task(self.bridge.audio(A, prefetch=True))
        await started.wait()
        foreground = asyncio.create_task(self.bridge.audio(A))
        await asyncio.sleep(.01)
        await self.bridge.cancel_prefetch(keep=set())
        self.assertFalse(preload.done())
        finish.set()
        first, second = await asyncio.gather(preload, foreground)
        self.assertEqual(first, second)
        self.assertEqual(calls, [A])
        await self.bridge.audio(A, prefetch=True)
        self.assertEqual(calls, [A])

    async def test_obsolete_download_cancelled_when_queue_changes(self):
        started = asyncio.Event()
        async def generate(key):
            started.set()
            await asyncio.Event().wait()
        self.bridge._generate = generate
        preload = asyncio.create_task(self.bridge.audio(A, prefetch=True))
        await started.wait()
        watcher = QueuePrefetch(self.bridge)
        async def call(command, args=None):
            return [{"queue_id": "room", "state": "playing", "current_index": 0}] if command.endswith("/all") else []
        watcher.call = call
        await watcher.scan()
        result = await asyncio.gather(preload, return_exceptions=True)
        self.assertIsInstance(result[0], asyncio.CancelledError)
        self.assertEqual(watcher.wanted, [])

    async def test_worker_prefetches_and_cache_reused(self):
        complete = asyncio.Event()
        calls = []
        async def generate(key):
            calls.append(key)
            path = self.bridge.cache / (key + ".mp3")
            path.write_bytes(b"fixture")
            complete.set()
            return path
        self.bridge._generate = generate
        watcher = QueuePrefetch(self.bridge)
        watcher.wanted = [A]
        worker = asyncio.create_task(watcher.work())
        watcher.wake.set()
        await asyncio.wait_for(complete.wait(), 1)
        await self.bridge.audio(A)
        worker.cancel()
        await asyncio.gather(worker, return_exceptions=True)
        self.assertEqual(calls, [A])
        self.assertEqual(watcher.snapshot()["cached"], [A])

    async def test_missing_configuration_does_not_contact_ma(self):
        self.bridge.options["music_assistant_token"] = ""
        watcher = QueuePrefetch(self.bridge)
        async def fail(*args):
            raise AssertionError("No network without configuration")
        watcher.scan = fail
        await watcher.run()
        self.assertFalse(watcher.configured)

    async def test_http_auth_error_does_not_expose_token(self):
        def handle(request):
            return httpx.Response(401)
        async with httpx.AsyncClient(transport=httpx.MockTransport(handle)) as client:
            watcher = QueuePrefetch(self.bridge, client)
            task = asyncio.create_task(watcher.run())
            await asyncio.sleep(.03)
            self.assertEqual(watcher.snapshot()["state"], "connection_error")
            self.assertNotIn("test-token", json.dumps(watcher.snapshot()))
            task.cancel()
            await asyncio.gather(task, return_exceptions=True)
