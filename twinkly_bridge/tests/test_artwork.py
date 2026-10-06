import io
import sys
import unittest
from pathlib import Path
from PIL import Image
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from bridge import Bridge, artwork_palette, frame_colors, validate_control

class ArtworkTest(unittest.TestCase):
    def image(self, color, size=(64,64)):
        output = io.BytesIO(); Image.new('RGB', size, color).save(output, 'PNG'); return output.getvalue()
    def test_colors_and_missing_cover(self):
        palette = artwork_palette(self.image((20, 180, 40)))
        self.assertEqual(palette[0], (20,180,40))
        self.assertEqual(frame_colors('mood',3,0,(255,0,0),[],palette=palette), [(20,180,40)]*3)
        self.assertEqual(frame_colors('mood',3,0,(255,0,0),[]), [(255,0,0)]*3)
        self.assertEqual(artwork_palette(b''), [])
    def test_input_bounds(self):
        with self.assertRaises(ValueError): artwork_palette(b'x'*262145)
        with self.assertRaises(ValueError): artwork_palette(self.image((0,0,0),(1024,1024)))
        with self.assertRaises(OSError): artwork_palette(b'bad image')
        with self.assertRaises(ValueError): validate_control({'cover_colors':'true'})
    def test_no_music_still_dark(self):
        self.assertEqual(frame_colors('music',3,0,(255,0,0),[],palette=[(20,180,40)]), [(0,0,0)]*3)
        colors = frame_colors('music',3,0,(255,0,0),[1,1,1],palette=[(20,180,40)])
        self.assertEqual(colors, [(20,180,40)]*3)
    def test_latest_cover_mailbox(self):
        bridge=Bridge({}); bridge.artwork(b'first'); bridge.artwork(b'second')
        self.assertEqual(bridge.cover_data,b'second')
        bridge.artwork(b'x'*262145); self.assertEqual(bridge.cover_data,b'second')
