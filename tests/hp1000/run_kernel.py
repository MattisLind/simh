"""Load unchanged 24397 KERN absolute records into L RAM and probe source entries.

This is an exploratory execution probe, not a diagnostic pass detector.
Octal 2 is the boot vector, 3000 is START, and the source comment also names 4.
"""
import argparse
import json
import re
from pathlib import Path

from absolute_binary import inspect
from run_baseline import execute


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--simulator", type=Path, default=Path("BIN/hp2100"))
    parser.add_argument("--image", type=Path, default=Path(
        "hp1000-references/software/diagnostics/archives/type-7/24397-16002_Rev-2001.abin"))
    parser.add_argument("--output", type=Path, default=Path("build/hp1000/kernel"))
    parser.add_argument("--steps", type=int, default=10000)
    parser.add_argument("--entry", type=lambda value: int(value, 8), action="append",
                        choices=[0o2, 0o3000, 0o4], help="probe only this octal entry; repeatable")
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    if args.steps <= 0:
        parser.error("--steps must be positive")
    try:
        info, memory = inspect(args.image)
        if any(a >= 32768 for a in memory):
            raise ValueError("image exceeds standard L memory")
        if [memory[i] for i in range(4)] != [0o160002, 2, 0o124003, 0o3000]:
            raise ValueError("image does not match the inspected Rev.2001 source anchors")
    except (OSError, ValueError) as exc:
        print(json.dumps({"status": "BLOCKED", "reason": str(exc)}))
        return 1
    results = []
    for entry in args.entry or [0o2, 0o3000, 0o4]:
        trace = args.output / f"entry-{entry:o}.trace"
        trace.write_text("")
        script = args.output / f"entry-{entry:o}.ini"
        script.write_text("set on\non error exit 1\nset cpu 1000-L\nset cpu 32K\nreset\n"
                          "assert LROMEN=0\n" +
                          "".join(f"deposit {a:o} {v:o}\n" for a, v in sorted(memory.items())) +
                          "".join(f"assert {a:o}={v:o}\n" for a, v in sorted(memory.items())) +
                          f"deposit P {entry:o}\nset debug {trace.resolve()}\n"
                          "set cpu debug=instr;data;reg\non error ignore\n"
                          f"step {args.steps}\non error exit 1\n"
                          "examine P,A,B,E,O,IR,LROMEN\nset nodebug\n"
                          "echo HP1000_CHECK_PASS\nexit\n")
        result = execute(args.simulator.resolve(), script, script.with_suffix(".log"), 30)
        output = script.with_suffix(".log").read_text() if script.with_suffix(".log").exists() else ""
        lines = trace.read_text().splitlines()
        instructions = [line for line in lines if line.startswith(">>CPU instr:")
                        and "simulation stop:" not in line]
        stops = [line for line in lines if "simulation stop:" in line]
        registers = dict(re.findall(r"^(P|A|B|E|O|IR|LROMEN):\s+([0-7]+)\s*$", output, re.M))
        diagnostic_status = "NOT_IMPLEMENTED" if "L-Series feature not yet emulated" in output else "UNKNOWN"
        results.append({"entry_octal": f"{entry:o}", "probe_status": result["status"],
                        "diagnostic_status": diagnostic_status, "diagnostic_pass_verified": False,
                        "image_sha256": info["sha256"], "records": len(info["records"]),
                        "words_loaded_and_asserted": len(memory),
                        "instruction_attempts": len(instructions), "registers_octal": registers,
                        "first_instructions": instructions[:5], "last_instructions": instructions[-5:],
                        "stop": stops[-1] if stops else "unresolved", "trace": str(trace),
                        "log": str(script.with_suffix(".log"))})
    (args.output / "results.json").write_text(json.dumps(results, indent=2) + "\n")
    for row in results:
        print(f"entry {row['entry_octal']}: {row['diagnostic_status']}, "
              f"{row['instruction_attempts']} attempts, P={row['registers_octal'].get('P')}, "
              f"IR={row['registers_octal'].get('IR')}")
    return int(any(row["probe_status"] != "PASS" for row in results))


if __name__ == "__main__":
    raise SystemExit(main())
