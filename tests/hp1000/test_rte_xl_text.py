"""Protect guest file payloads and original media during host text import."""
import tempfile
import unittest
from pathlib import Path
from rte_7920 import make_image, read_volume
from rte_records import encode_text, decode_text
from rte_xl_put_text import put_text


class TextImportTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.image = self.root / 'working.disc'
        self.source = self.root / 'source.mac'
        self.source.write_text('MACRO,R\n      NAM TEST,3\n      END\n')
        self.files = {'SOURCE': (3, encode_text('OLD SOURCE\n')), 'BINARY': (6, bytes(range(256)) * 4)}
        make_image(self.image, {1: self.files, 2: {'OTHER': (3, encode_text('OTHER VOLUME\n'))}})

    def test_append_and_replace_preserve_existing_payloads(self):
        before = self.image.read_bytes()
        put_text(self.image, self.source, '&DEMO')
        after = read_volume(self.image, 1)
        for name, value in self.files.items():
            self.assertEqual(after[name], value)
        self.assertEqual(decode_text(after['&DEMO'][1]), self.source.read_text())
        self.source.write_text('REPLACEMENT\n')
        put_text(self.image, self.source, '&DEMO', replace=True)
        after = read_volume(self.image, 1)
        self.assertEqual(decode_text(after['&DEMO'][1]), 'REPLACEMENT\n')
        for name, value in self.files.items():
            self.assertEqual(after[name], value)
        # Adjacent logical volumes, including all their metadata, stay exact.
        self.assertEqual(self.image.read_bytes()[83 * 5 * 12288 * 2:],
                         before[83 * 5 * 12288 * 2:])

    def test_existing_name_requires_replace_and_binary_is_protected(self):
        before = self.image.read_bytes()
        with self.assertRaisesRegex(ValueError, 'file exists'):
            put_text(self.image, self.source, 'SOURCE')
        with self.assertRaisesRegex(ValueError, 'only ASCII'):
            put_text(self.image, self.source, 'BINARY', replace=True)
        self.assertEqual(self.image.read_bytes(), before)

    def test_reference_media_guard(self):
        reference = self.root / 'hp1000-references' / 'original.disc'
        with self.assertRaisesRegex(ValueError, 'original reference'):
            put_text(reference, self.source, 'SOURCE')


if __name__ == '__main__':
    unittest.main()
