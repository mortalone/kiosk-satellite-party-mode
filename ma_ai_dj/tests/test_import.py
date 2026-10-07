import importlib.util
import json
import tempfile
import unittest
from pathlib import Path

spec = importlib.util.spec_from_file_location('ma_start', Path(__file__).parents[1] / 'start.py')
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


class ImportTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.data = self.root / 'data'
        self.source = self.root / 'source'
        self.data.mkdir()
        self.source.mkdir()
        (self.source / 'settings.json').write_text(json.dumps({'server_id': 'original'}))
        (self.source / 'library.db').write_bytes(b'existing library')
        (self.source / 'options.json').write_text('old addon options')

    def test_requires_explicit_import_and_complete_data(self):
        with self.assertRaises(ValueError):
            module.import_data(self.data, self.source, False)
        (self.source / 'library.db').unlink()
        with self.assertRaises(ValueError):
            module.import_data(self.data, self.source, True)
        self.assertFalse((self.data / 'ma-data').exists())

    def test_retains_identity_without_overwriting_on_restart(self):
        target = module.import_data(self.data, self.source, True)
        self.assertEqual((target / 'library.db').read_bytes(), b'existing library')
        self.assertFalse((target / 'options.json').exists())
        (target / 'settings.json').write_text('{"server_id": "retained"}')
        self.assertEqual(module.import_data(self.data, self.source, True), target)
        self.assertEqual(json.loads((target / 'settings.json').read_text())['server_id'], 'retained')

    def test_refuses_symlink_and_partial_target(self):
        (self.source / 'link').symlink_to(self.root)
        with self.assertRaises(ValueError):
            module.import_data(self.data, self.source, True)
        (self.data / 'ma-data').mkdir()
        with self.assertRaises(ValueError):
            module.import_data(self.data, self.source, True)
