"""Decode the local HP PROM programmer A/S hex containers without modifying them."""
import argparse
import hashlib
import json
import re
from pathlib import Path


def decode_prom(data):
    match = re.fullmatch(rb"\x02\$A([0-9A-F]{4}),\s*(.*?)\s*\x03\$S([0-9A-F]{4})\s*",
                         data, re.S)
    if not match:
        raise ValueError("invalid PROM A/S framing")
    body = match[2]
    if not re.fullmatch(rb"(?:[0-9A-F]{2}\s+)*[0-9A-F]{2}", body.strip()):
        raise ValueError("invalid PROM hex payload")
    payload = bytes.fromhex(body.decode("ascii"))
    checksum = int(match[3], 16)
    if sum(payload) & 65535 != checksum:
        raise ValueError("PROM checksum mismatch")
    return int(match[1], 16), payload, checksum


def read_pair(low_path, high_path):
    lanes, manifest = [], []
    for path in [low_path, high_path]:
        original = path.read_bytes()
        start, lane, checksum = decode_prom(original)
        if start != 0 or len(lane) != 4096:
            raise ValueError("expected a 4096-byte PROM lane starting at zero")
        lanes.append(lane)
        manifest.append({"path": str(path), "sha256": hashlib.sha256(original).hexdigest(),
                         "bytes": len(lane), "checksum": f"{checksum:04X}"})
    # Lane order is confirmed by source anchors, not inferred from filenames.
    words = [(h << 8) | l for l, h in zip(*lanes)]
    if words[:3] != [0, 0o4002, 0o24100]:
        raise ValueError("PROM pair does not match source opening words")
    return words, manifest


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path(
        "hp1000-references/software/diagnostics/archives/type-4"))
    parser.add_argument("--output", type=Path, default=Path("build/hp1000/firmware"))
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    try:
        words, lanes = read_pair(args.root / "12001-16001_Rev-2140.src",
                                 args.root / "12001-16002_Rev-2150.src")
    except (ValueError, OSError) as exc:
        print(json.dumps({"status": "BLOCKED", "reason": str(exc)}))
        return 1
    binary = b"".join(w.to_bytes(2, "big") for w in words)
    (args.output / "processor-rom.bin").write_bytes(binary)
    report = {"status": "PASS", "scope": "container integrity and three source anchors only",
              "revision_consistency": "Not assessed by this command; see source-report.json",
              "lanes_low_then_high": lanes, "words": len(words),
              "image_sha256": hashlib.sha256(binary).hexdigest()}
    (args.output / "prom-report.json").write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps(report, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
