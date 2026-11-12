"""Inspect HP absolute paper-tape records without executing or altering them.

Record layout and additive checksum follow HP2100/hp2100_sys.c sim_load
and the PTR binary loaders in HP2100/hp2100_pt.c. This is a format check,
not evidence that the program supports any particular CPU.
"""
import argparse
import hashlib
import json
from pathlib import Path


def decode(data):
    records, memory = [], {}
    pos = 0
    while pos < len(data):
        if data[pos] == 0:  # NUL leader, inter-record padding, or trailer
            pos += 1
            continue
        offset, count = pos, data[pos]
        end = pos + 6 + count * 2
        if end > len(data):
            raise ValueError(f"truncated record at byte {offset}")
        address = int.from_bytes(data[pos + 2:pos + 4], "big")
        if address + count > 65536:
            raise ValueError(f"address overflow at byte {offset}")
        words = [int.from_bytes(data[i:i + 2], "big")
                 for i in range(pos + 4, end - 2, 2)]
        checksum = int.from_bytes(data[end - 2:end], "big")
        if (address + sum(words)) & 65535 != checksum:
            raise ValueError(f"checksum mismatch at byte {offset}")
        records.append({"offset": offset, "address": address, "count": count,
                        "checksum": checksum})
        # Preserve load order: later records can deliberately overwrite words.
        memory.update((address + i, word) for i, word in enumerate(words))
        pos = end
    if not records:
        raise ValueError("no absolute binary records")
    return records, memory


def inspect(path):
    data = path.read_bytes()
    records, memory = decode(data)
    return {"path": str(path), "sha256": hashlib.sha256(data).hexdigest(),
            "status": "PASS", "scope": "record format and checksums only",
            "records": records, "unique_words": len(memory),
            "first_address": min(memory), "last_address": max(memory)}, memory


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("image", type=Path)
    parser.add_argument("--deposits", type=Path,
                        help="write SIMH deposit commands; does not run the image")
    args = parser.parse_args()
    try:
        result, memory = inspect(args.image)
        if args.deposits:
            args.deposits.write_text("".join(f"deposit {a:o} {v:o}\n"
                                            for a, v in sorted(memory.items())))
    except (OSError, ValueError) as exc:
        print(json.dumps({"status": "FAIL", "reason": str(exc)}))
        return 1
    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
