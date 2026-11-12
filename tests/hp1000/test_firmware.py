"""PROM framing, integrity, and source-comparison inputs."""
import unittest
from pathlib import Path

from firmware import decode_prom, read_pair
from firmware_source import expression, resolve


class PromTests(unittest.TestCase):
    fixture = b"\x02$A0000,\r\n00 FF 10\r\n\x03$S010F\r\n"

    def test_known_checksum(self):
        self.assertEqual(decode_prom(self.fixture), (0, b"\0\xff\x10", 0x10f))

    def test_corruption(self):
        with self.assertRaisesRegex(ValueError, "checksum"):
            decode_prom(self.fixture.replace(b"FF", b"FE"))

    def test_reject_bad_frames(self):
        for data in [b"", self.fixture[1:], self.fixture + b"00", self.fixture.replace(b"FF", b"F")]:
            with self.subTest(data=data), self.assertRaises(ValueError):
                decode_prom(data)

    def test_expressions(self):
        self.assertEqual(expression("1763B+P0", {"P0": 0o4000}, 0), 0o5763)
        self.assertEqual(expression("*+3-P0", {"P0": 0o4000}, 0o4100), 0o103)
        self.assertEqual(expression("-11", {}, 0, 8), -0o11)
        with self.assertRaises(ValueError):
            expression("MISSING", {}, 0)

    def test_source_origins_repeats_and_forward_equates(self):
        symbols, records = resolve("      ORG 4000B\nSTART EQU LAST+1\n"
                                   "      REP 3\n      NOP\nLAST  OCT 4\n")
        self.assertEqual(symbols["START"], 0o4004)
        self.assertEqual([r[1] for r in records], list(range(0o4000, 0o4004)))

    def test_original_lanes(self):
        root = Path("hp1000-references/software/diagnostics/archives/type-4")
        lo, hi = root / "12001-16001_Rev-2140.src", root / "12001-16002_Rev-2150.src"
        if not lo.exists() or not hi.exists():
            self.skipTest("private HP PROM files unavailable")
        words, manifest = read_pair(lo, hi)
        self.assertEqual(len(words), 4096)
        self.assertEqual(words[:3], [0, 0o4002, 0o24100])
        self.assertEqual([m["checksum"] for m in manifest], ["E7A6", "23FF"])


if __name__ == "__main__":
    unittest.main()
