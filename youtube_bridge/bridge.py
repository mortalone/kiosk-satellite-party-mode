"""YouTube -> OpenSubsonic bridge for unmodified Music Assistant servers."""
from __future__ import annotations

import asyncio
import hashlib
import hmac
import json
import logging
import os
import re
import shutil
import signal
import sqlite3
import sys
import tempfile
import time
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import parse_qs, urlparse
from xml.etree import ElementTree as ET

from fastapi import FastAPI, Request
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse, RedirectResponse, Response

LOG = logging.getLogger("youtube_bridge")
VIDEO_ID = re.compile(r"^[A-Za-z0-9_-]{11}$")
VERSION = "0.1.3"


class BridgeError(Exception):
    def __init__(self, message: str, code: int = 0):
        super().__init__(message)
        self.code = code


def video_id(value: str) -> str | None:
    value = value.strip()
    if VIDEO_ID.fullmatch(value):
        return value
    parsed = urlparse(value)
    host = (parsed.hostname or "").lower()
    if host == "youtu.be":
        candidate = parsed.path.strip("/").split("/")[0]
    elif host in {"youtube.com", "www.youtube.com", "m.youtube.com", "music.youtube.com"}:
        candidate = parse_qs(parsed.query).get("v", [""])[0]
        if parsed.path.startswith(("/shorts/", "/embed/", "/live/")):
            candidate = parsed.path.split("/")[2]
    else:
        return None
    return candidate if VIDEO_ID.fullmatch(candidate) else None


def artist_id(name: str) -> str:
    return "artist-" + hashlib.sha256(name.encode()).hexdigest()[:20]


def now() -> str:
    return datetime.now(timezone.utc).isoformat()


def load_options() -> dict:
    path = Path(os.getenv("BRIDGE_OPTIONS", "/data/options.json"))
    return json.loads(path.read_text()) if path.exists() else {}


class Bridge:
    def __init__(self, options: dict, data: Path):
        self.options = options
        self.username = str(options.get("username", "youtube"))
        self.password = str(options.get("password", ""))
        self.limit = min(30, max(1, int(options.get("search_limit", 10))))
        self.cache_mb = max(128, int(options.get("cache_mb", 512)))
        self.max_minutes = max(1, int(options.get("max_track_minutes", 120)))
        self.lyrics_enabled = options.get("lyrics_enabled", True)
        self.allow_auto_lyrics = options.get("allow_auto_lyrics", False)
        self.data = data
        data.mkdir(parents=True, exist_ok=True)
        self.cache = data / "cache"
        self.cache.mkdir(exist_ok=True)
        self.db = sqlite3.connect(data / "catalog.db")
        self.db.row_factory = sqlite3.Row
        self.db.execute("PRAGMA journal_mode=WAL")
        self.db.execute("CREATE TABLE IF NOT EXISTS tracks (id TEXT PRIMARY KEY, payload TEXT NOT NULL, saved INTEGER NOT NULL DEFAULT 0, starred TEXT, added TEXT NOT NULL)")
        self.db.execute("CREATE TABLE IF NOT EXISTS playlists (id TEXT PRIMARY KEY, name TEXT NOT NULL, entries TEXT NOT NULL, created TEXT NOT NULL)")
        self.db.execute("CREATE TABLE IF NOT EXISTS lyrics (id TEXT NOT NULL, policy INTEGER NOT NULL, payload TEXT NOT NULL, expires REAL NOT NULL, PRIMARY KEY(id,policy))")
        self.db.commit()
        self.jobs = asyncio.Semaphore(2)
        self.search_cache: dict[str, tuple[float, list[dict]]] = {}
        self.audio_tasks: dict[str, asyncio.Task] = {}
        self.background_audio: set[str] = set()
        self.foreground_audio: dict[str, int] = {}
        self.lyrics_tasks: dict[tuple[str, bool], asyncio.Task] = {}
        self.lyrics_wait_seconds = 8
        # Pinned files cannot be evicted while being served to MA.
        self.readers: dict[str, int] = {}
        self.cache_lock = asyncio.Lock()
        self.generation_lock = asyncio.Lock()
        self.pending: set[str] = set()

    def authenticate(self, params) -> bool:
        if not self.password or params.get("u") != self.username:
            return False
        if params.get("t") and params.get("s"):
            expected = hashlib.md5((self.password + params["s"]).encode()).hexdigest()
            return hmac.compare_digest(expected.encode(), params["t"].encode())
        password = params.get("p", "")
        if password.startswith("enc:"):
            try:
                password = bytes.fromhex(password[4:]).decode()
            except (ValueError, UnicodeError):
                return False
        return hmac.compare_digest(self.password.encode(), password.encode())

    def unpin(self, key: str):
        remaining = self.readers.get(key, 1) - 1
        if remaining:
            self.readers[key] = remaining
        else:
            self.readers.pop(key, None)

    def put(self, info: dict, saved: bool = False) -> dict:
        item_id = info.get("id", "")
        if not VIDEO_ID.fullmatch(item_id):
            raise BridgeError("Invalid YouTube video ID", 10)
        old = self.db.execute("SELECT payload FROM tracks WHERE id=?", (item_id,)).fetchone()
        previous = json.loads(old[0]) if old else {}
        artist = info.get("artist") or info.get("uploader") or info.get("channel") or previous.get("artist") or "YouTube"
        duration = int(info.get("duration") or previous.get("duration") or 0)
        if info.get("is_live") or info.get("live_status") in {"is_live", "is_upcoming"}:
            raise BridgeError("Live broadcasts are not supported in this version", 70)
        if duration > self.max_minutes * 60:
            raise BridgeError(f"Video exceeds the {self.max_minutes} minute limit", 70)
        item = {"id": item_id, "title": info.get("title") or previous.get("title") or item_id,
                "artist": artist, "artistId": artist_id(artist), "album": info.get("title") or previous.get("title") or item_id,
                "albumId": "album-" + item_id, "duration": duration, "coverArt": item_id,
                "isDir": False, "type": "music", "contentType": "audio/mpeg", "suffix": "mp3",
                "bitRate": 192, "samplingRate": 44100, "channelCount": 2,
                "size": max(1, duration * 24000), "created": previous.get("created") or now(),
                "track": 1}
        self.db.execute("INSERT INTO tracks(id,payload,saved,added) VALUES(?,?,?,?) ON CONFLICT(id) DO UPDATE SET payload=excluded.payload,saved=MAX(tracks.saved,excluded.saved)",
                        (item_id, json.dumps(item), int(saved), now()))
        self.db.commit()
        return item

    def tracks(self, saved: bool = False) -> list[dict]:
        rows = self.db.execute("SELECT payload,starred FROM tracks" + (" WHERE saved=1" if saved else "") + " ORDER BY added DESC")
        items = []
        for row in rows:
            item = json.loads(row[0])
            if row[1]:
                item["starred"] = row[1]
            items.append(item)
        return items

    def find(self, item_id: str) -> dict | None:
        row = self.db.execute("SELECT payload,starred FROM tracks WHERE id=?", (item_id,)).fetchone()
        if not row:
            return None
        item = json.loads(row[0])
        if row[1]:
            item["starred"] = row[1]
        return item

    async def command(self, args: list[str], timeout: int = 90) -> str:
        base = [sys.executable, "-m", "yt_dlp", "--ignore-config", "--no-warnings", "--no-progress",
                "--socket-timeout", "15", "--retries", "1", "--extractor-retries", "1",
                "--js-runtimes", "node", "--no-playlist"]
        cookies = self.data / "cookies.txt"
        if cookies.exists():
            base += ["--cookies", str(cookies)]
        async with self.jobs:
            proc = await asyncio.create_subprocess_exec(*base, *args, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE,
                                                        start_new_session=True)
            try:
                stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout)
            except BaseException:
                if proc.returncode is None:
                    try:
                        os.killpg(proc.pid, signal.SIGKILL)
                    except ProcessLookupError:
                        pass
                await proc.wait()
                raise
        if proc.returncode:
            # yt-dlp's full stderr may contain signed URLs or cookie data.
            error = stderr.decode(errors="replace").lower()
            reason = "YouTube extraction failed"
            if "not a bot" in error:
                reason = "YouTube requests verification; anonymous playback is blocked"
            elif "certificate" in error:
                reason = "YouTube connection certificate could not be verified"
            elif "private" in error or "unavailable" in error:
                reason = "Video is private, unavailable or restricted"
            elif "format" in error:
                reason = "YouTube did not provide a usable audio format"
            elif "file is larger" in error or "max-filesize" in error:
                reason = "Audio exceeds the cache size limit"
            raise BridgeError(reason, 70)
        return stdout.decode()

    async def detail(self, item_id: str, saved: bool = False) -> dict:
        if not VIDEO_ID.fullmatch(item_id):
            raise BridgeError("Invalid video ID", 10)
        existing = self.find(item_id)
        if existing:
            if saved:
                self.db.execute("UPDATE tracks SET saved=1 WHERE id=?", (item_id,))
                self.db.commit()
            return existing
        output = await self.command(["--skip-download", "--dump-single-json", "https://www.youtube.com/watch?v=" + item_id])
        return self.put(json.loads(output), saved)

    async def caption_command(self, item_id: str, allow_auto: bool) -> dict:
        cookies = self.data / "cookies.txt"
        proc = await asyncio.create_subprocess_exec(
            sys.executable, str(Path(__file__).with_name("captions.py")), item_id,
            "1" if allow_auto else "0", str(cookies) if cookies.exists() else "",
            stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.DEVNULL)
        try:
            output, _ = await asyncio.wait_for(proc.communicate(), 35)
        except BaseException:
            if proc.returncode is None:
                proc.kill()
            await proc.wait()
            raise
        if proc.returncode:
            raise BridgeError("Caption lookup failed")
        return json.loads(output)

    async def fetch_lyrics(self, item_id: str, policy: bool) -> list[dict]:
        try:
            result = await self.caption_command(item_id, policy)
            lyrics = result.get("lyrics") or []
            failed = result.get("failed", False)
            if result.get("automatic") and not policy:
                lyrics = []
            # Positive cache: 7 days; missing captions: 1 hour; failed lookup: 5 minutes.
            ttl = 300 if failed else (7 * 86400 if lyrics else 3600)
        except Exception:
            LOG.debug("Caption lookup unavailable for video %s", item_id)
            lyrics, ttl = [], 300
        self.db.execute("INSERT OR REPLACE INTO lyrics VALUES(?,?,?,?)",
                        (item_id, int(policy), json.dumps(lyrics), time.time() + ttl))
        self.db.commit()
        return lyrics

    async def lyrics(self, item_id: str) -> list[dict]:
        if not self.lyrics_enabled or not VIDEO_ID.fullmatch(item_id):
            return []
        policy = bool(self.allow_auto_lyrics)
        row = self.db.execute("SELECT payload,expires FROM lyrics WHERE id=? AND policy=?",
                              (item_id, int(policy))).fetchone()
        if row and row["expires"] > time.time():
            return json.loads(row["payload"])
        key = (item_id, policy)
        task = self.lyrics_tasks.get(key)
        if task is None:
            # Captions cannot consume every worker while audio is starting.
            if len(self.lyrics_tasks) >= 2:
                return []
            task = asyncio.create_task(self.fetch_lyrics(item_id, policy))
            self.lyrics_tasks[key] = task
            def done(completed):
                self.lyrics_tasks.pop(key, None)
                if not completed.cancelled():
                    completed.exception()
            task.add_done_callback(done)
        try:
            return await asyncio.wait_for(asyncio.shield(task), self.lyrics_wait_seconds)
        except (Exception, asyncio.CancelledError) as exc:
            if isinstance(exc, asyncio.CancelledError):
                raise
            # Slow extraction continues in the background; no error reaches MA.
            return []

    async def search(self, query: str, count: int) -> list[dict]:
        direct = video_id(query)
        if direct:
            return [await self.detail(direct)]
        if not query.strip():
            return self.tracks(saved=True)
        query = query.strip()[:250]
        cached = self.search_cache.get(query)
        if cached and time.monotonic() - cached[0] < 300:
            return cached[1][:count]
        result = await self.command(["--flat-playlist", "--skip-download", "--dump-single-json", f"ytsearch{self.limit}:{query}"])
        entries = json.loads(result).get("entries") or []
        tracks = []
        for entry in entries:
            try:
                tracks.append(self.put(entry))
            except BridgeError:
                continue
        if len(self.search_cache) >= 100:
            self.search_cache.pop(next(iter(self.search_cache)))
        self.search_cache[query] = (time.monotonic(), tracks)
        return tracks[:count]

    async def prune(self, incoming: int = 0):
        async with self.cache_lock:
            files = sorted(self.cache.glob("*.mp3"), key=lambda p: p.stat().st_mtime)
            total = sum(p.stat().st_size for p in files)
            budget = self.cache_mb * 1024 * 1024
            for path in files:
                if total + incoming <= budget:
                    break
                if self.readers.get(path.stem) or path.stem in self.pending:
                    continue
                total -= path.stat().st_size
                path.unlink(missing_ok=True)
            if total + incoming > budget:
                raise BridgeError("Cache is full while other tracks are playing; try again shortly")

    async def generate(self, item_id: str) -> Path:
        async with self.generation_lock:
            self.pending.add(item_id)
            try:
                return await self._generate(item_id)
            finally:
                self.pending.discard(item_id)

    async def _generate(self, item_id: str) -> Path:
        # Full metadata prevents accidentally downloading long videos or live streams.
        result = await self.command(["--skip-download", "--dump-single-json", "https://www.youtube.com/watch?v=" + item_id])
        self.put(json.loads(result))
        await self.prune()
        with tempfile.TemporaryDirectory(dir=self.cache, prefix="work-") as tmp:
            output = str(Path(tmp) / "audio.%(ext)s")
            await self.command(["-f", "bestaudio/best", "-x", "--audio-format", "mp3", "--audio-quality", "192K",
                                "--postprocessor-args", "ffmpeg:-ar 44100 -ac 2",
                                "--max-filesize", str(self.cache_mb) + "M", "-o", output,
                                "https://www.youtube.com/watch?v=" + item_id], timeout=300)
            source = Path(tmp) / "audio.mp3"
            if not source.is_file() or source.stat().st_size == 0:
                raise BridgeError("YouTube did not return playable audio", 70)
            await self.prune(source.stat().st_size)
            target = self.cache / (item_id + ".mp3")
            shutil.move(source, target)
            os.utime(target, None)
            return target

    async def cancel_prefetch(self, keep: set[str]):
        tasks = []
        for key in list(self.background_audio):
            if key in keep or self.foreground_audio.get(key):
                continue
            if task := self.audio_tasks.get(key):
                task.cancel()
                tasks.append(task)
        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)

    async def audio(self, item_id: str, prefetch: bool = False) -> Path:
        if not prefetch and VIDEO_ID.fullmatch(item_id) and (self.cache / (item_id + ".mp3")).is_file():
            # Normal playback/Range reads of cached audio must not interrupt preloading.
            return await self._audio(item_id, False)
        if not prefetch:
            self.foreground_audio[item_id] = self.foreground_audio.get(item_id, 0) + 1
            try:
                # Reuse an in-flight download for this track; cancel other background work.
                await self.cancel_prefetch(keep={item_id})
                return await self._audio(item_id, False)
            finally:
                self.foreground_audio[item_id] -= 1
                if not self.foreground_audio[item_id]:
                    self.foreground_audio.pop(item_id)
        return await self._audio(item_id, True)

    async def _audio(self, item_id: str, prefetch: bool) -> Path:
        await self.detail(item_id)
        path = self.cache / (item_id + ".mp3")
        if path.exists():
            os.utime(path, None)
            return path
        task = self.audio_tasks.get(item_id)
        if task is not None and task.cancelling():
            await asyncio.gather(task, return_exceptions=True)
            task = self.audio_tasks.get(item_id)
        if task is None:
            if prefetch and self.foreground_audio:
                raise BridgeError("Foreground audio has priority")
            task = asyncio.create_task(self.generate(item_id))
            self.audio_tasks[item_id] = task
            if prefetch:
                self.background_audio.add(item_id)
            def done(completed):
                if self.audio_tasks.get(item_id) is completed:
                    self.audio_tasks.pop(item_id, None)
                    self.background_audio.discard(item_id)
                if not completed.cancelled():
                    completed.exception()  # retrieve errors when HTTP requester disconnected
            task.add_done_callback(done)
        return await asyncio.shield(task)

    def album(self, item: dict, songs: bool = False) -> dict:
        value = {"id": item["albumId"], "name": item["album"], "artist": item["artist"], "artistId": item["artistId"],
                 "coverArt": item["id"], "songCount": 1, "duration": item["duration"], "created": item["created"]}
        if songs:
            value["song"] = [item]
        return value

    def artists(self) -> list[dict]:
        result: dict[str, dict] = {}
        for item in self.tracks():
            result.setdefault(item["artistId"], {"id": item["artistId"], "name": item["artist"], "albumCount": 0, "coverArt": item["id"]})["albumCount"] += 1
        return list(result.values())

    def playlists(self) -> list[dict]:
        result = []
        for row in self.db.execute("SELECT * FROM playlists ORDER BY created"):
            ids = json.loads(row["entries"])
            songs = [self.find(i) for i in ids if self.find(i)]
            result.append({"id": row["id"], "name": row["name"], "songCount": len(songs), "duration": sum(s["duration"] for s in songs),
                           "created": row["created"], "changed": row["created"], "owner": self.username, "public": False, "entry": songs})
        return result

    async def dispatch(self, action: str, params) -> dict:
        def integer(name, default=0):
            try:
                return min(1000, max(0, int(params.get(name, default))))
            except ValueError:
                raise BridgeError(f"Invalid {name}", 10) from None
        def required(name):
            if not params.get(name):
                raise BridgeError(f"Missing {name}", 10)
            return params[name]
        if action == "ping":
            return {}
        if action == "getLicense":
            return {"license": {"valid": True}}
        if action == "getOpenSubsonicExtensions":
            return {"openSubsonicExtensions": [{"name": "songLyrics", "versions": [1]}]}
        if action == "search3":
            query = params.get("query", "")
            songs = await self.search(query, integer("songCount", 20) + integer("songOffset"))
            matched = self.tracks() if not query else songs
            artists = [a for a in self.artists() if not query or query.casefold() in a["name"].casefold()]
            albums = [self.album(s) for s in matched]
            so, ao, ar = integer("songOffset"), integer("albumOffset"), integer("artistOffset")
            return {"searchResult3": {"song": songs[so:so + integer("songCount", 20)],
                      "album": albums[ao:ao + integer("albumCount", 20)], "artist": artists[ar:ar + integer("artistCount", 20)]}}
        if action == "getSong":
            return {"song": await self.detail(required("id"))}
        if action == "getAlbum":
            key = required("id")
            if not key.startswith("album-"):
                raise BridgeError("Album not found", 70)
            return {"album": self.album(await self.detail(key[6:]), songs=True)}
        if action == "getAlbumInfo2":
            return {"albumInfo": {}}
        if action == "getLyrics":
            # Legacy clients use title/artist; refuse ambiguous cover/version matches.
            items = [t for t in self.tracks() if t["title"] == params.get("title")
                     and t["artist"] == params.get("artist")]
            if not items:
                # Older MA providers pass title/artist positionally in reverse order.
                items = [t for t in self.tracks() if t["title"] == params.get("artist")
                         and t["artist"] == params.get("title")]
            lyrics = await self.lyrics(items[0]["id"]) if len(items) == 1 else []
            if lyrics:
                return {"lyrics": {"artist": items[0]["artist"], "title": items[0]["title"],
                                   "value": "\n".join(line["value"] for line in lyrics[0]["line"])}}
            raise BridgeError("Lyrics not found", 70)
        if action == "getLyricsBySongId":
            return {"lyricsList": {"structuredLyrics": await self.lyrics(required("id"))}}
        if action == "getArtistInfo2":
            return {"artistInfo2": {"similarArtist": []}}
        if action == "getArtist":
            key = required("id")
            items = [t for t in self.tracks() if t["artistId"] == key]
            if not items:
                raise BridgeError("Artist not found", 70)
            return {"artist": {"id": key, "name": items[0]["artist"], "albumCount": len(items), "album": [self.album(t) for t in items]}}
        if action == "getArtists":
            return {"artists": {"ignoredArticles": "", "index": [{"name": "YouTube", "artist": self.artists()}]}}
        if action == "getAlbumList2":
            items = self.tracks(saved=True)
            offset, size = integer("offset"), integer("size", 20)
            return {"albumList2": {"album": [self.album(t) for t in items[offset:offset + size]]}}
        if action == "getMusicFolders":
            return {"musicFolders": {"musicFolder": [{"id": 1, "name": "YouTube"}]}}
        if action == "getGenres":
            return {"genres": {"genre": []}}
        if action in {"star", "unstar"}:
            ids = params.getlist("id")
            for key in ids:
                await self.detail(key, saved=action == "star")
                self.db.execute("UPDATE tracks SET starred=? WHERE id=?", (now() if action == "star" else None, key))
            self.db.commit()
            return {}
        if action == "getStarred2":
            return {"starred2": {"artist": [], "album": [], "song": [s for s in self.tracks() if s.get("starred")]}}
        if action == "getPlaylists":
            return {"playlists": {"playlist": [{k: v for k, v in p.items() if k != "entry"} for p in self.playlists()]}}
        if action == "getPlaylist":
            value = next((p for p in self.playlists() if p["id"] == required("id")), None)
            if value is None:
                raise BridgeError("Playlist not found", 70)
            return {"playlist": value}
        if action == "createPlaylist":
            key = params.get("playlistId") or "playlist-" + os.urandom(8).hex()
            ids = params.getlist("songId")
            for key_id in ids:
                await self.detail(key_id, saved=True)
            existing = next((p for p in self.playlists() if p["id"] == key), None)
            name = params.get("name") or (existing["name"] if existing else "YouTube playlist")
            self.db.execute("INSERT OR REPLACE INTO playlists VALUES(?,?,?,?)", (key, name, json.dumps(ids), now()))
            self.db.commit()
            return {"playlist": next(p for p in self.playlists() if p["id"] == key)}
        if action == "updatePlaylist":
            key = required("playlistId")
            playlist = next((p for p in self.playlists() if p["id"] == key), None)
            if not playlist:
                raise BridgeError("Playlist not found", 70)
            remove = {int(v) for v in params.getlist("songIndexToRemove")}
            ids = [s["id"] for i, s in enumerate(playlist["entry"]) if i not in remove]
            for key_id in params.getlist("songIdToAdd"):
                await self.detail(key_id, saved=True)
                ids.append(key_id)
            self.db.execute("UPDATE playlists SET name=?,entries=? WHERE id=?", (params.get("name", playlist["name"]), json.dumps(ids), key))
            self.db.commit()
            return {}
        if action == "deletePlaylist":
            self.db.execute("DELETE FROM playlists WHERE id=?", (required("id"),))
            self.db.commit()
            return {}
        if action in {"scrobble", "setRating"}:
            return {}
        empty = {"getPodcasts": ("podcasts", "channel"), "getNewestPodcasts": ("newestPodcasts", "episode"),
                 "getInternetRadioStations": ("internetRadioStations", "internetRadioStation"),
                 "getSimilarSongs2": ("similarSongs2", "song"), "getTopSongs": ("topSongs", "song"),
                 "getBookmarks": ("bookmarks", "bookmark"), "getLyricsBySongId": ("lyricsList", "structuredLyrics")}
        if action in empty:
            parent, child = empty[action]
            return {parent: {child: []}}
        raise BridgeError(f"Unsupported action: {action}", 0)


def protocol_response(params, payload: dict | None = None, error: BridgeError | None = None):
    body = {"status": "failed" if error else "ok", "version": "1.16.1", "type": "youtube-bridge",
            "serverVersion": VERSION, "openSubsonic": True}
    body.update({"error": {"code": error.code, "message": str(error)}} if error else payload or {})
    if params.get("f", "xml") == "json":
        return JSONResponse({"subsonic-response": body})
    root = ET.Element("subsonic-response", {"xmlns": "http://subsonic.org/restapi"})
    def fill(element, value):
        for name, content in value.items():
            if isinstance(content, list):
                for item in content:
                    child = ET.SubElement(element, name)
                    if isinstance(item, dict):
                        fill(child, item)
                    else:
                        child.text = str(item)
            elif isinstance(content, dict):
                fill(ET.SubElement(element, name), content)
            elif content is not None:
                if name == "value" and element.tag in {"line", "lyrics"}:
                    element.text = str(content)
                else:
                    element.set(name, str(content).lower() if isinstance(content, bool) else str(content))
    fill(root, body)
    return Response(ET.tostring(root, encoding="utf-8", xml_declaration=True), media_type="text/xml")


class PinnedFileResponse(FileResponse):
    def __init__(self, bridge: Bridge, key: str, path: Path):
        self.bridge, self.key = bridge, key
        super().__init__(path, media_type="audio/mpeg")

    async def __call__(self, scope, receive, send):
        try:
            return await super().__call__(scope, receive, send)
        finally:
            self.bridge.unpin(self.key)


def make_app(bridge: Bridge, ui: bool = False) -> FastAPI:
    @asynccontextmanager
    async def lifespan(app):
        yield
        tasks = list(bridge.audio_tasks.values()) + list(bridge.lyrics_tasks.values())
        for task in tasks:
            task.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)
    app = FastAPI(lifespan=lifespan)

    @app.get("/health")
    async def health():
        return {"status": "ok", "version": VERSION, "configured": bool(bridge.password)}

    if not ui:
        @app.api_route("/rest/{action}", methods=["GET", "HEAD", "POST"])
        async def rest(action: str, request: Request):
            from starlette.datastructures import QueryParams
            params = request.query_params
            if request.method == "POST":
                params = QueryParams((await request.body()).decode())
            if not bridge.authenticate(params):
                return protocol_response(params, error=BridgeError("Wrong username or password", 40))
            action = action.removesuffix(".view")
            try:
                if action in {"stream", "download"}:
                    key = params.get("id", "")
                    bridge.readers[key] = bridge.readers.get(key, 0) + 1
                    try:
                        path = await bridge.audio(key)
                        return PinnedFileResponse(bridge, key, path)
                    except BaseException:
                        bridge.unpin(key)
                        raise
                if action == "getCoverArt":
                    key = params.get("id", "").removeprefix("album-")
                    if not VIDEO_ID.fullmatch(key):
                        track = next((s for s in bridge.tracks() if s["artistId"] == key), None)
                        if not track:
                            raise BridgeError("Artwork not found", 70)
                        key = track["id"]
                    return RedirectResponse("https://i.ytimg.com/vi/" + key + "/hqdefault.jpg")
                return protocol_response(params, await bridge.dispatch(action, params))
            except (BridgeError, asyncio.TimeoutError, ValueError, json.JSONDecodeError) as exc:
                if not isinstance(exc, BridgeError):
                    exc = BridgeError("YouTube request timed out or returned invalid data")
                if action == "getLyrics" and exc.code == 70:
                    LOG.debug("Lyrics not found")
                else:
                    LOG.warning("%s failed: %s", action, exc)
                return protocol_response(params, error=exc)
    else:
        @app.get("/", response_class=HTMLResponse)
        async def index():
            return Path(__file__).with_name("index.html").read_text()

        @app.post("/import")
        async def import_link(request: Request):
            try:
                value = await request.json()
                key = video_id(str(value.get("url", "")))
                if key is None:
                    return JSONResponse({"error": "Indsæt et gyldigt YouTube-link eller video-ID."}, status_code=400)
                item = await bridge.detail(key, saved=True)
                return {"track": item, "search": "https://www.youtube.com/watch?v=" + key}
            except (BridgeError, asyncio.TimeoutError, ValueError) as exc:
                return JSONResponse({"error": str(exc)}, status_code=502)

        @app.get("/catalog")
        async def catalog():
            return {"tracks": bridge.tracks(saved=True), "username": bridge.username, "version": VERSION}
        @app.get("/prefetch-status")
        async def prefetch_status():
            watcher = getattr(bridge, "prefetch", None)
            return watcher.snapshot() if watcher else {"enabled": False, "configured": False, "state": "disabled"}
    return app


async def main():
    import uvicorn
    from queue_prefetch import QueuePrefetch
    options = load_options()
    if len(str(options.get("password", ""))) < 8:
        raise SystemExit("Set a bridge password of at least 8 characters in the addon configuration before starting.")
    bridge = Bridge(options, Path(os.getenv("BRIDGE_DATA", "/data")))
    # Stale work directories come only from interrupted downloads.
    for path in bridge.cache.glob("work-*"):
        if path.is_dir():
            shutil.rmtree(path)
    await bridge.prune()
    bridge.prefetch = QueuePrefetch(bridge)
    watcher = asyncio.create_task(bridge.prefetch.run())
    LOG.info("YouTube Bridge %s: MA source port 8102; Home Assistant ingress port 8099", VERSION)
    servers = [uvicorn.Server(uvicorn.Config(make_app(bridge), host="0.0.0.0", port=8102, access_log=False)),
               uvicorn.Server(uvicorn.Config(make_app(bridge, ui=True), host="0.0.0.0", port=8099, access_log=False))]
    try:
        await asyncio.gather(*(s.serve() for s in servers))
    finally:
        watcher.cancel()
        await asyncio.gather(watcher, return_exceptions=True)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    asyncio.run(main())
