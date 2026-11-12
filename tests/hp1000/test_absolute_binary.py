"""Negative format tests and an optional independent original-source anchor."""
import unittest
from pathlib import Path

from absolute_binary import decode


class AbsoluteBinaryTests(unittest.TestCase):
    # One word at octal 100, value octal 1234, checksum octal 1334.
    record = bytes.fromhex("01000040029c02dc")

    def test_record_and_padding(self):
        records, memory = decode(b"\0\0" + self.record + b"\0" * 10)
        self.assertEqual(memory, {0o100: 0o1234})
        self.assertEqual(records[0]["offset"], 2)

    def test_corruption(self):
        with self.assertRaisesRegex(ValueError, "checksum"):
            decode(self.record[:-1] + b"\0")

    def test_truncation(self):
        for length in range(1, len(self.record)):
            with self.subTest(length=length), self.assertRaises(ValueError):
                decode(self.record[:length])

    def test_empty(self):
        with self.assertRaisesRegex(ValueError, "no absolute"):
            decode(b"\0" * 10)

    def test_original_kernel_source_anchor(self):
        path = Path("hp1000-references/software/diagnostics/archives/type-7/"
                    "24397-16002_Rev-2001.abin")
        if not path.exists():
            self.skipTest("private HP reference image unavailable")
        records, memory = decode(path.read_bytes())
        self.assertEqual(len(records), 114)
        # 24397-18002 Rev.2001: ORG 0B / OCT 160002 / OCT 2;
        # ORG 2 / JMP *+1,I / DEF START; START is at octal 3000.
        self.assertEqual([memory[i] for i in range(4)],
                         [0o160002, 2, 0o124003, 0o3000])


if __name__ == "__main__":
    unittest.main()
