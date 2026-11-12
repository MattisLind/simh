import unittest
from rte_records import encode_text, decode_text


class Records(unittest.TestCase):
    def test_word_lengths_padding_and_eof(self):
        data = encode_text('LI,CP\n\nMS,32\n')
        self.assertEqual(data[:18], b'\x00\x03LI,CP \x00\x03\x00\x00\x00\x00\x00\x03MS')
        self.assertEqual(len(data) % 256, 0)
        self.assertEqual(decode_text(data), 'LI,CP\n\nMS,32\n')

    def test_corrupt_trailer_rejected(self):
        with self.assertRaises(ValueError):
            decode_text(b'\x00\x01AB\x00\x02\xff\xff')

    def test_missing_eof_rejected(self):
        with self.assertRaises(ValueError):
            decode_text(b'\x00\x01AB\x00\x01')
