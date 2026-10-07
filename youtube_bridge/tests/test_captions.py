import json
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from captions import parse_captions, select_caption


class CaptionTests(unittest.TestCase):
    def test_json3_timing_entities_and_duplicate_cues(self):
        events = [{"tStartMs": 1200, "segs": [{"utf8": "One &amp; "}, {"utf8": "two"}]},
                  {"tStartMs": 1200, "segs": [{"utf8": "One &amp; two"}]},
                  {"tStartMs": 5000, "segs": [{"utf8": "One &amp; two"}]},
                  {"tStartMs": 0}, {"tStartMs": -1, "segs": [{"utf8": "Bad"}]}]
        self.assertEqual(parse_captions(json.dumps({"events": events}), "json3"),
                         [{"start": 1200, "value": "One & two"}, {"start": 5000, "value": "One & two"}])

    def test_vtt_timing_tags_and_multiline(self):
        text = "WEBVTT\n\n1\n00:01.250 --> 00:02.500\n<c>First</c> line\nsecond line\n\n00:01:02.345 --> 00:01:05.000 align:start\nLast &amp; line\n"
        self.assertEqual(parse_captions(text, "vtt"), [{"start": 1250, "value": "First line second line"}, {"start": 62345, "value": "Last & line"}])

    def test_uploader_preferred_original_language(self):
        info = {"language": "fr", "subtitles": {"en": [{"ext": "json3", "url": "https://youtube.com/en"}],
                                                "fr": [{"ext": "json3", "url": "https://youtube.com/fr"}]},
                "automatic_captions": {"fr-orig": [{"ext": "json3", "url": "https://youtube.com/auto"}]}}
        lang, track, automatic = select_caption(info, True)
        self.assertEqual((lang, automatic), ("fr", False))

    def test_auto_opt_in_and_machine_translation_rejected(self):
        info = {"automatic_captions": {"en": [{"ext": "json3", "url": "https://youtube.com/subs?tlang=en"}],
                                       "fr-orig": [{"ext": "json3", "url": "https://youtube.com/subs?lang=fr"}]}}
        self.assertIsNone(select_caption(info, False))
        self.assertEqual(select_caption(info, True)[0], "fr")
        info["automatic_captions"].pop("fr-orig")
        self.assertIsNone(select_caption(info, True))

    def test_vtt_fallback_and_no_captions(self):
        self.assertIsNone(select_caption({}, True))
        info = {"subtitles": {"en": [{"ext": "vtt", "url": "https://youtube.com/subs"}]}}
        self.assertEqual(select_caption(info, False)[1]["ext"], "vtt")
