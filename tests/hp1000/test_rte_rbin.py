import struct
import unittest
from rte_rbin import encode, decode


class RelocatableTests(unittest.TestCase):
    def sample(self):
        payload = [0x2000, 0x4142, 0x4344, 0x4546]
        return struct.pack('>6H', 0x0600, payload[0], sum(payload) & 65535, *payload[1:])

    def test_preserve_records_including_header_checksum(self):
        raw = self.sample() * 2
        wrapped, info = encode(raw)
        self.assertEqual(decode(wrapped), raw)
        self.assertEqual(info['module_names'], ['ABCDEF', 'ABCDEF'])
        self.assertEqual(len(wrapped) % 256, 0)

    def test_corruption_and_truncation_rejected(self):
        raw = bytearray(self.sample())
        raw[-1] ^= 1
        with self.assertRaisesRegex(ValueError, 'checksum'):
            encode(raw)
        with self.assertRaisesRegex(ValueError, 'truncated'):
            encode(self.sample()[:-1])

    def test_disk_envelope_corruption_rejected(self):
        wrapped, _ = encode(self.sample())
        raw = bytearray(wrapped)
        raw[15] ^= 1
        with self.assertRaises(ValueError):
            decode(raw)
