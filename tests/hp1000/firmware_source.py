"""Resolve the directives used by 12001-18001 and compare with decoded PROMs.

This is a narrow source verifier, not an HP assembler replacement: instruction
encoding is delegated to the existing HP2100 symbolic assembler, with failures
reported. Sources and decoded PROM bytes are never patched to force agreement.
"""
import argparse
import hashlib
import json
import re
import subprocess
from pathlib import Path

from firmware import read_pair


def expression(text, symbols, address, radix=10):
    value = 0
    for part in re.findall(r"[+-]?[^+-]+", text):
        sign = -1 if part.startswith("-") else 1
        token = part.lstrip("+-")
        if token == "*":
            number = address
        elif token in symbols:
            number = symbols[token]
        elif re.fullmatch(r"[0-7]+B", token):
            number = int(token[:-1], 8)
        elif re.fullmatch(r"\d+", token):
            number = int(token, radix)
        else:
            raise ValueError(f"unresolved expression {text!r} ({token})")
        value += sign * number
    return value


def resolve(source):
    address, repeat = 0, 1
    symbols, equates, records = {}, [], []
    for line_number, line in enumerate(source.splitlines(), 1):
        if not line.strip() or line.startswith("*") or line.startswith("ASMB,"):
            continue
        fields = line.split()
        label = "" if line[0].isspace() else fields.pop(0)
        operation = fields.pop(0)
        operand_ops = {"EQU", "ORG", "REP", "OCT", "DEC", "DEF", "ASC",
                       "AND", "XOR", "IOR", "JMP", "JSB", "ISZ", "ADA", "ADB",
                       "CPA", "CPB", "LDA", "LDB", "STA", "STB", "LIA", "LIB",
                       "MIA", "MIB", "OTA", "OTB", "STC", "CLC", "STF", "CLF",
                       "SFS", "SFC", "SOS", "SOC", "HLT", "MPY", "DIV", "DLD", "DST",
                       "ASL", "ASR", "LSL", "LSR", "RRR", "RRL"}
        operand = fields[0] if fields and operation in operand_ops else ""
        if operation in ["SOS", "SOC"] and operand != "C":
            operand = ""
        if operation in ["HED", "SUP", "SKP", "SPC", "END"]:
            continue
        if operation == "EQU":
            equates.append((label, operand, address))
            try:
                symbols[label] = expression(operand, symbols, address)
            except ValueError:
                pass
            continue
        if operation == "ORG":
            address = expression(operand, symbols, address)
            continue
        if operation == "REP":
            repeat = expression(operand, symbols, address)
            continue
        if label:
            if label in symbols:
                raise ValueError(f"duplicate label {label} at line {line_number}")
            symbols[label] = address
        for _ in range(repeat):
            size = 2 if operation in ["MPY", "DIV", "DLD", "DST"] else 1
            if operation == "ASC":
                size = int(operand.split(",")[0])
            records.append((line_number, address, operation, operand, size))
            address += size
        repeat = 1
    for _ in range(len(equates) + 1):
        pending = []
        for label, operand, address in equates:
            try:
                symbols[label] = expression(operand, symbols, address)
            except ValueError:
                pending.append((label, operand, address))
        if not pending:
            return symbols, records
        if len(pending) == len(equates):
            raise ValueError(f"unresolved equates: {pending}")
        equates = pending
    raise ValueError("equate resolution failed")


def commands_for(symbols, records):
    commands, addresses = [], {}
    for line, address, operation, operand, size in records:
        if not 0o4000 <= address < 0o14000:
            raise ValueError(f"source line {line}: address outside four ROM pages")
        for i in range(size):
            if address + i in addresses:
                raise ValueError(f"overlap at source line {line}")
            addresses[address + i] = line
        if operation == "ASC":
            count, text = operand.split(",", 1)
            text = text.ljust(int(count) * 2)
            for i in range(size):
                commands.append(f"deposit {address+i:o} {ord(text[2*i])*256+ord(text[2*i+1]):o}")
        elif operation in ["OCT", "DEC", "DEF"]:
            parts = operand.split(",")
            value = expression(parts[0], symbols, address, 8 if operation == "OCT" else 10)
            if parts[1:] == ["I"]:
                value |= 0o100000
            commands.append(f"deposit {address:o} {value & 65535:o}")
        else:
            if operand and not (operation in ["SOS", "SOC"] and operand == "C"):
                parts = operand.split(",")
                target = expression(parts[0], symbols, address)
                operand = (str(target) if operation in ["ASL", "ASR", "LSL", "LSR", "RRR", "RRL"]
                           else f"{target & 65535:o}") + ("," + ",".join(parts[1:]) if parts[1:] else "")
            commands.append(f"deposit {address:o} {operation} {operand}".rstrip())
    return commands, addresses


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path(
        "hp1000-references/software/diagnostics/archives/type-4"))
    parser.add_argument("--simulator", type=Path, default=Path("BIN/hp2100"))
    parser.add_argument("--output", type=Path, default=Path("build/hp1000/firmware"))
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    source_path = args.root / "12001-18001_Rev-2150.src"
    try:
        symbols, records = resolve(source_path.read_text())
        commands, addresses = commands_for(symbols, records)
        words, _ = read_pair(args.root / "12001-16001_Rev-2140.src",
                             args.root / "12001-16002_Rev-2150.src")
        script = args.output / "source-compare.ini"
        script.write_text("set on\non error exit 1\nset cpu 1000-E\nset cpu 32K\n" +
                          "\n".join(commands) + "\necho SOURCE_ASSEMBLED\n" +
                          "examine 4000-13777\nexit\n")
        result = subprocess.run([str(args.simulator.resolve()), str(script.resolve())],
                                input="", text=True, stdout=subprocess.PIPE,
                                stderr=subprocess.STDOUT, timeout=30)
        (args.output / "source-compare.log").write_text(result.stdout)
        if result.returncode or "SOURCE_ASSEMBLED\n" not in result.stdout:
            raise ValueError("symbolic assembly failed; see source-compare.log")
        assembled = {int(a, 8): int(w, 8) for a, w in
                     re.findall(r"^(\d+):\s+([0-7]{6})\s*$", result.stdout, re.M)}
        if len(assembled) != 4096:
            raise ValueError(f"expected 4096 examined words, got {len(assembled)}")
        differences = [{"address": f"{a:o}", "line": line,
                        "source": f"{assembled[a]:06o}", "prom": f"{words[a-0o4000]:06o}"}
                       for a, line in sorted(addresses.items()) if assembled[a] != words[a-0o4000]]
        report = {"status": "PASS" if not differences else "FAIL",
                  "scope": "source-emitted words only; unassigned ROM padding is excluded",
                  "source_words": len(addresses), "differences": differences,
                  "source_sha256": hashlib.sha256(source_path.read_bytes()).hexdigest(),
                  "image_sha256": hashlib.sha256(b"".join(w.to_bytes(2, "big") for w in words)).hexdigest(),
                  "symbols": {name: f"{value:o}" for name, value in sorted(symbols.items())}}
    except (OSError, ValueError, subprocess.TimeoutExpired) as exc:
        report = {"status": "BLOCKED", "reason": str(exc)}
    (args.output / "source-report.json").write_text(json.dumps(report, indent=2) + "\n")
    print(report["status"], report.get("reason", f"{report.get('source_words')} source words, "
                                           f"{len(report.get('differences', []))} differences"))
    return int(report["status"] != "PASS")


if __name__ == "__main__":
    raise SystemExit(main())
