"""Index local references without changing original files (Python stdlib only)."""
import argparse
import csv
import hashlib
import re
from collections import Counter
from pathlib import Path

from absolute_binary import decode


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path("hp1000-references"))
    parser.add_argument("--output", type=Path, default=Path("build/hp1000/inventory.csv"))
    args = parser.parse_args()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    counts = Counter()
    with args.output.open("w", newline="") as stream:
        writer = csv.writer(stream)
        writer.writerow(["path", "bytes", "sha256", "part", "revision",
                         "source_header", "absolute_records", "format_status"])
        for path in sorted(args.root.rglob("*")):
            if not path.is_file():
                continue
            data = path.read_bytes()
            match = re.search(r"(\d{5}-\d{5})(?:_Rev-([^_.]+))?", path.name)
            header, records, status = "", "", "UNKNOWN"
            if path.suffix == ".src":
                header = next((s.strip() for s in data.decode("latin1").splitlines()
                               if s.strip()), "")
            elif path.suffix == ".abin":
                try:
                    decoded, _ = decode(data)
                    records, status = len(decoded), "PASS"
                except ValueError as exc:
                    status = "UNKNOWN: " + str(exc)
            writer.writerow([path.as_posix(), len(data), hashlib.sha256(data).hexdigest(),
                             match[1] if match else "", match[2] or "" if match else "",
                             header, records, status])
            counts[path.suffix] += 1
    print(dict(sorted(counts.items())))
    print(args.output)


if __name__ == "__main__":
    main()
