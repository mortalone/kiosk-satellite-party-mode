"""Fetch a video's captions in a separate, time-limited subprocess."""
import html
import json
import re
import sys
from urllib.parse import parse_qs, urlparse

MAX_BYTES = 2 * 1024 * 1024


def clean(value):
    return " ".join(html.unescape(re.sub(r"<[^>]*>", "", value)).split())


def parse_captions(text, fmt):
    lines = []
    if fmt == "json3":
        for event in json.loads(text).get("events", []):
            value = clean("".join(s.get("utf8", "") for s in event.get("segs", [])))
            start = event.get("tStartMs")
            if value and isinstance(start, (int, float)) and start >= 0:
                lines.append({"start": int(start), "value": value})
    else:
        def millis(value):
            parts = value.replace(",", ".").split(":")
            return int(round(sum(float(p) * 60 ** i for i, p in enumerate(reversed(parts))) * 1000))
        for block in re.split(r"\n\s*\n", text.replace("\r\n", "\n")):
            rows = block.splitlines()
            for i, row in enumerate(rows):
                match = re.match(r"\s*((?:\d+:)?\d+:\d+[.,]\d+)\s+-->", row)
                if match:
                    value = clean(" ".join(rows[i + 1:]))
                    if value:
                        lines.append({"start": millis(match[1]), "value": value})
                    break
    # Keep repetitions at different times (choruses), remove identical duplicate cues.
    unique = {(line["start"], line["value"]): line for line in lines}
    return sorted(unique.values(), key=lambda line: line["start"])[:10000]


def select_caption(info, allow_auto):
    language = (info.get("language") or "").split("-")[0]
    for automatic, table in [(False, info.get("subtitles") or {}),
                             (True, info.get("automatic_captions") or {} if allow_auto else {})]:
        choices = []
        for lang, formats in table.items():
            if lang == "live_chat":
                continue
            for track in formats:
                if track.get("ext") not in {"json3", "vtt"} or not track.get("url"):
                    continue
                # Do not silently replace original words with machine translations.
                if parse_qs(urlparse(track["url"]).query).get("tlang"):
                    continue
                rank = (lang.split("-")[0] != language if language else False,
                        not lang.endswith("-orig"), track["ext"] != "json3", lang)
                choices.append((rank, lang, track, automatic))
        if choices:
            _, lang, track, automatic = min(choices, key=lambda row: row[0])
            return lang.removesuffix("-orig"), track, automatic
    return None


def fetch(video_id, allow_auto, cookies):
    from yt_dlp import YoutubeDL
    class QuietLogger:
        def debug(self, message): pass
        def warning(self, message): pass
        def error(self, message): pass
    options = {"quiet": True, "no_warnings": True, "logger": QuietLogger(),
               "skip_download": True, "noplaylist": True, "socket_timeout": 10,
               "retries": 0, "extractor_retries": 0, "js_runtimes": {"node": {}}}
    if cookies:
        options["cookiefile"] = cookies
    with YoutubeDL(options) as ydl:
        info = ydl.extract_info("https://www.youtube.com/watch?v=" + video_id, download=False)
        selected = select_caption(info, allow_auto)
        if not selected:
            return {"lyrics": []}
        lang, track, automatic = selected
        with ydl.urlopen(track["url"]) as response:
            data = response.read(MAX_BYTES + 1)
        if len(data) > MAX_BYTES:
            raise ValueError("Caption file too large")
        lines = parse_captions(data.decode("utf-8-sig"), track["ext"])
        return {"lyrics": [{"lang": lang, "synced": True, "line": lines}] if lines else [],
                "automatic": automatic}


if __name__ == "__main__":
    try:
        if not re.fullmatch(r"[A-Za-z0-9_-]{11}", sys.argv[1]):
            raise ValueError("Invalid video ID")
        print(json.dumps(fetch(sys.argv[1], sys.argv[2] == "1", sys.argv[3] or None)))
    except Exception:
        # Never print upstream errors containing cookies or signed caption URLs.
        print(json.dumps({"lyrics": [], "failed": True}))
