"""Run KERN Rev.2001's complete word-memory phase, then probe the next phase.

No diagnostic or emulator patching: source-derived completion/error breakpoints
bound the original execution. Hardware parity-interrupt testing is a separate
phase and must never be counted as part of this memory-phase pass.
"""
import argparse
import hashlib
import json
import time
from pathlib import Path

from absolute_binary import inspect
from firmware_source import resolve
from run_baseline import execute


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--simulator", type=Path, default=Path("BIN/hp2100"))
    parser.add_argument("--source", type=Path, default=Path(
        "hp1000-references/software/diagnostics/archives/type-4/24397-18002_Rev-2001.src"))
    parser.add_argument("--image", type=Path, default=Path(
        "hp1000-references/software/diagnostics/archives/type-7/24397-16002_Rev-2001.abin"))
    parser.add_argument("--output", type=Path, default=Path("build/hp1000/kernel-memory"))
    parser.add_argument("--steps", type=int, default=50000000)
    parser.add_argument("--parity", action="store_true",
                        help="also verify the complete parity-error interrupt phase")
    args = parser.parse_args()
    if args.steps <= 0:
        parser.error("--steps must be positive")
    args.output.mkdir(parents=True, exist_ok=True)
    result_path = args.output / "results.json"
    try:
        info, memory = inspect(args.image)
        source = args.source.read_bytes()
        symbols, _ = resolve(source.decode("ascii"))
        expected = {"START": 0o3000, "PEIT": 0o3641, "MERR": 0o3214,
                    "DSPLY": 0o3311, "FADD": 0o3773, "LADD": 0o3774,
                    "EOM": 0o525, "PRERR": symbols["PRERR"]}
        if any(symbols[name] != address for name, address in expected.items()):
            raise ValueError("source layout differs from inspected KERN Rev.2001")
        # Independent source/binary anchors at the phase boundary. This checks
        # the resolver's location counting, rather than trusting labels alone.
        if [memory[0], memory[1], memory[2], memory[3]] != [0o160002, 2, 0o124003, 0o3000]:
            raise ValueError("binary entry does not match inspected source")
        signature = [0o63733, 0o70526, 0o14102, 0o3666, 0o2400, 0o70475, 0o106705]
        if [memory[symbols["PEIT"] + i] for i in range(len(signature))] != signature:
            raise ValueError("binary PEIT signature does not match source boundary")
        if max(memory) >= 32768:
            raise ValueError("image exceeds configured standard L memory")
    except (OSError, ValueError, KeyError) as exc:
        result = {"status": "BLOCKED", "reason": str(exc)}
        result_path.write_text(json.dumps(result, indent=2) + "\n")
        print(result)
        return 1

    # MERR and DSPLY also execute in page zero when KERN moves its current page
    # out of the way to test it. Break on executable entry, not return storage.
    errors = {symbols[name] + 1 for name in ["MERR", "DSPLY", "PRERR"]}
    errors.update(symbols[name] + 1 - 0o2000 for name in ["MERR", "DSPLY"])
    trace = args.output / "parity-entry.trace"
    trace.write_text("")
    script = args.output / "full-memory.ini"
    commands = ["set on", "on error exit 1", "set cpu 1000-L", "set cpu 32K",
                "reset", "assert LROMEN=0"]
    commands.extend(f"deposit {a:o} {v:o}" for a, v in sorted(memory.items()))
    commands.extend(f"assert {a:o}={v:o}" for a, v in sorted(memory.items()))
    commands.extend(f"break {a:o}" for a in sorted(errors | {symbols["PEIT"]}))
    commands.extend(["deposit P 2", "on error ignore", f"step {args.steps}",
                     "on error exit 1", "examine P,A,B,E,O,IR",
                     "examine 3773-3774", "examine 525", "assert P=3641",
                     "assert IR=027641", "assert 3773=020000", "assert 3774=077777",
                     "assert 525=077777", "echo KERN_MEMORY_PHASE_COMPLETE", "nobreak all"])
    if args.parity:
        commands.extend(f"break {a:o}" for a in sorted(errors | {symbols["TST01"]}))
        commands.extend(["on error ignore", "step 1000000", "on error exit 1",
                         "examine P,A,B,IR,LPAR,LPAREN,LPAREVEN,LPFAULT,LPFETCH",
                         f"assert P={symbols['TST01']:o}", "assert LPFAULT=513", "assert LPFETCH=1",
                         f"assert LPAR={0o100000 | symbols['BADIN']:o}",
                         "assert LPAREN=1", "assert LPAREVEN=0",
                         "echo KERN_PARITY_PHASE_COMPLETE", "nobreak all"])
    commands.extend([
                     f"set debug {trace.resolve()}", "set cpu debug=instr;data;reg",
                     "on error ignore", "step 10000", "on error exit 1",
                     "examine P,A,B,E,O,IR", "set nodebug", "echo HP1000_CHECK_PASS", "exit"])
    script.write_text("\n".join(commands) + "\n")
    start = time.monotonic()
    run = execute(args.simulator.resolve(), script, script.with_suffix(".log"), 30)
    elapsed = time.monotonic() - start
    log = script.with_suffix(".log").read_text() if script.with_suffix(".log").exists() else ""
    completed = "KERN_MEMORY_PHASE_COMPLETE\n" in log
    parity_completed = "KERN_PARITY_PHASE_COMPLETE\n" in log
    next_status = "NOT_IMPLEMENTED" if "L-Series feature not yet emulated" in log else "UNKNOWN"
    result = {"memory_phase": "PASS" if completed else run["status"] if run["status"] != "PASS" else "UNKNOWN",
              "scope": ("KERN word-memory and parity-error interrupt phases for 32KW standard L" if args.parity
                        else "KERN word-memory phase for 32KW standard L; parity phase not verified"),
              "full_KERN_pass": False, "next_phase": next_status,
              "parity_phase": "PASS" if parity_completed else "UNKNOWN",
              "parity_requested": args.parity,
              "verified_parity_faults": 513 if parity_completed else None,
              "verified_fetch_faults": 1 if parity_completed else None,
              "image_sha256": info["sha256"], "source_sha256": hashlib.sha256(source).hexdigest(),
              "records_validated": len(info["records"]), "words_loaded_and_asserted": len(memory),
              "entry_octal": "2", "completion_octal": f"{symbols['PEIT']:o}",
              "error_breakpoints_octal": [f"{a:o}" for a in sorted(errors)],
              "final_memory_range_octal": ["20000", "77777"] if completed else None,
              "instruction_budget": args.steps, "wall_time_limit_seconds": 30,
              "elapsed_seconds": round(elapsed, 3), "log": str(script.with_suffix(".log")),
              "next_phase_trace": str(trace), "execution_status": run["status"]}
    result_path.write_text(json.dumps(result, indent=2) + "\n")
    print(f"Memory: {result['memory_phase']}; parity: {result['parity_phase']}; next phase: {next_status}")
    print(result_path)
    return int(not completed or (args.parity and not parity_completed) or run["status"] != "PASS")


if __name__ == "__main__":
    raise SystemExit(main())
