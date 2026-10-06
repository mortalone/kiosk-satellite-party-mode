"""Contract tests use MA's exact OpenSubsonic client over real local HTTP."""
import asyncio
import importlib.util
import json
import socket
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from urllib.parse import parse_qs, urlparse
from unittest.mock import patch

import httpx
import uvicorn
from libopensonic import AsyncConnection
from starlette.datastructures import QueryParams

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from bridge import Bridge, BridgeError, make_app, protocol_response, video_id

ID = "3VaZ-4AG-f0"
OTHER = "dQw4w9WgXcQ"
INFO = {"id": ID, "title": "L'accordéoniste — cover", "uploader": "Tinalei", "duration": 63}


class ContractTests(unittest.IsolatedAsyncioTestCase):
    @classmethod
    def setUpClass(cls):
        cls.mp3 = subprocess.run(["ffmpeg", "-v", "error", "-f", "lavfi", "-i", "sine=frequency=440:duration=0.2", "-ar", "44100", "-ac", "2", "-b:a", "192k", "-f", "mp3", "pipe:1"], check=True, stdout=subprocess.PIPE).stdout

    async def asyncSetUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.bridge = Bridge({"username": "youtube", "password": "test-password"}, Path(self.temp.name))
        self.calls = []
        async def command(args, timeout=90):
            self.calls.append(args)
            if any(a.startswith("ytsearch") for a in args):
                return json.dumps({"entries": [INFO, {"id": OTHER, "title": "Other song", "uploader": "Other artist", "duration": 80}]})
            if "--dump-single-json" in args:
                return json.dumps(INFO)
            if "-o" in args:
                Path(args[args.index("-o") + 1].replace("%(ext)s", "mp3")).write_bytes(self.mp3)
                return ""
            raise AssertionError(args)
        self.bridge.command = command
        self.sock = socket.socket()
        self.sock.bind(("127.0.0.1", 0))
        self.port = self.sock.getsockname()[1]
        self.server = uvicorn.Server(uvicorn.Config(make_app(self.bridge), log_level="critical", access_log=False))
        self.server_task = asyncio.create_task(self.server.serve(sockets=[self.sock]))
        for _ in range(100):
            if self.server.started:
                break
            await asyncio.sleep(.01)
        self.conn = AsyncConnection("http://127.0.0.1", username="youtube", password="test-password", port=self.port, use_get=True, app_name="Music Assistant")

    async def asyncTearDown(self):
        if self.conn._sess:
            await self.conn._sess.close()
        self.server.should_exit = True
        await self.server_task
        self.bridge.db.close()
        self.temp.cleanup()

    async def test_ma_client_login_and_extensions(self):
        self.assertTrue(await self.conn.ping())
        self.assertEqual(await self.conn.get_open_subsonic_extensions(), [])
        self.assertTrue((await self.conn.get_license())["license"]["valid"])
        async with httpx.AsyncClient(trust_env=False) as client:
            r = await client.get(f"http://127.0.0.1:{self.port}/rest/ping.view", params={"f": "json", "u": "youtube", "p": "wrong"})
            self.assertEqual(r.json()["subsonic-response"]["error"]["code"], 40)

    async def test_search_album_artist_metadata(self):
        result = await self.conn.search3("Tinalei", song_count=10)
        self.assertEqual(result.song[0].id, ID)
        self.assertEqual(result.song[0].content_type, "audio/mpeg")
        self.assertEqual(result.song[0].channel_count, 2)
        song = await self.conn.get_song(ID)
        album = await self.conn.get_album(song.album_id)
        self.assertEqual(album.song[0].id, ID)
        await self.conn.get_album_info2(song.album_id)
        artist = await self.conn.get_artist(song.artist_id)
        self.assertEqual(artist.name, "Tinalei")
        await self.conn.get_artist_info2(song.artist_id)
        await self.conn.get_artists()
        await self.conn.get_album_list2("newest")

    async def test_exact_link_and_restart(self):
        result = await self.conn.search3("https://www.youtube.com/shorts/" + ID, song_count=10)
        self.assertEqual(result.song[0].id, ID)
        replacement = Bridge({"username": "youtube", "password": "test-password"}, Path(self.temp.name))
        async def fail(*a, **k):
            raise AssertionError("Persisted metadata must not need upstream lookup")
        replacement.command = fail
        self.assertEqual((await replacement.detail(ID))["title"], INFO["title"])
        replacement.db.close()

    async def test_source_favorites_and_playlists(self):
        await self.conn.search3("Tinalei", song_count=10)
        await self.conn.star(sids=[ID])
        self.assertEqual((await self.conn.get_starred2()).song[0].id, ID)
        self.assertEqual((await self.conn.search3("", song_count=10)).song[0].id, ID)
        await self.conn.create_playlist(name="YouTube", song_ids=[ID])
        playlists = await self.conn.get_playlists()
        self.assertEqual(len(playlists), 1)
        playlist = await self.conn.get_playlist(playlists[0].id)
        self.assertEqual(playlist.entry[0].id, ID)
        await self.conn.update_playlist(playlists[0].id, name="Renamed", song_ids_to_add=[OTHER])
        self.assertEqual((await self.conn.get_playlist(playlists[0].id)).song_count, 2)

    async def test_ma_audio_url_range_and_cache(self):
        await self.conn.search3("Tinalei", song_count=10)
        url, _ = self.conn.get_stream_url(ID, tformat="raw", estimate_length=True)
        async with httpx.AsyncClient(trust_env=False) as client:
            response = await client.get(url, headers={"Range": "bytes=0-9"})
            self.assertEqual(response.status_code, 206)
            self.assertEqual(len(response.content), 10)
            self.assertEqual(response.headers["content-type"], "audio/mpeg")
            self.assertTrue(response.content.startswith(b"ID3"))
            calls = len(self.calls)
            again = await client.get(url)
            self.assertEqual(again.status_code, 200)
            decoded = await asyncio.create_subprocess_exec("ffmpeg", "-v", "error", "-i", "pipe:0", "-f", "null", "-", stdin=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE)
            _, error = await decoded.communicate(again.content)
            self.assertEqual(decoded.returncode, 0, error.decode())
            self.assertEqual(len(self.calls), calls)
            bad = await client.get(url, headers={"Range": "bytes=99999-"})
            self.assertEqual(bad.status_code, 416)
        self.assertEqual(self.bridge.readers, {})

    async def test_xml_post_and_missing_item(self):
        async with httpx.AsyncClient(trust_env=False) as client:
            base = f"http://127.0.0.1:{self.port}/rest/"
            r = await client.post(base + "ping.view", data={"u": "youtube", "p": "test-password", "f": "xml"})
            self.assertIn('status="ok"', r.text)
            r = await client.get(base + "getSong.view", params={"u": "youtube", "p": "test-password", "f": "json", "id": "invalid"})
            self.assertEqual(r.json()["subsonic-response"]["error"]["code"], 10)

    async def test_link_import_ingress(self):
        transport = httpx.ASGITransport(app=make_app(self.bridge, ui=True))
        async with httpx.AsyncClient(transport=transport, base_url="http://ingress") as client:
            bad = await client.post("/import", json={"url": "http://127.0.0.1/private"})
            self.assertEqual(bad.status_code, 400)
            good = await client.post("/import", json={"url": "https://youtu.be/" + ID})
            self.assertEqual(good.json()["track"]["id"], ID)
            catalog = await client.get("/catalog")
            self.assertEqual(catalog.json()["tracks"][0]["id"], ID)

    async def test_audio_generation_is_deduplicated(self):
        self.bridge.put(INFO)
        first, second = await asyncio.gather(self.bridge.audio(ID), self.bridge.audio(ID))
        self.assertEqual(first, second)
        self.assertEqual(sum("-o" in c for c in self.calls), 1)

    async def test_unicode_password(self):
        self.bridge.password = "æøå-password"
        self.assertTrue(self.bridge.authenticate(QueryParams({"u": "youtube", "p": "æøå-password"})))
        self.assertFalse(self.bridge.authenticate(QueryParams({"u": "youtube", "t": "ø", "s": "salt"})))

    async def test_failed_stream_releases_pin(self):
        async with httpx.AsyncClient(trust_env=False) as client:
            await client.get(f"http://127.0.0.1:{self.port}/rest/stream", params={"u": "youtube", "p": "test-password", "id": "invalid", "f": "json"})
        self.assertEqual(self.bridge.readers, {})

    async def test_long_or_live_and_invalid_ids_rejected(self):
        for info in [dict(INFO, duration=100000), dict(INFO, is_live=True), dict(INFO, id="../../escape")]:
            with self.assertRaises(BridgeError):
                self.bridge.put(info)


class InputTests(unittest.TestCase):
    def test_only_youtube_video_urls(self):
        self.assertEqual(video_id("https://www.youtube.com/watch?v=" + ID), ID)
        self.assertEqual(video_id("https://youtu.be/" + ID + "?t=10"), ID)
        self.assertEqual(video_id(ID), ID)
        for bad in ["https://youtube.com.evil/watch?v=" + ID, "file:///etc/passwd", "http://localhost/watch?v=" + ID, "../../escape"]:
            self.assertIsNone(video_id(bad))


if __name__ == "__main__":
    unittest.main()
