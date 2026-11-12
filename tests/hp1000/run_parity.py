"""Independent L RAM/SC 5 tests, including fault delivery and bad-fetch inhibition."""
import argparse
import json
from pathlib import Path

from run_baseline import execute


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--simulator", type=Path, default=Path("BIN/hp2100"))
    parser.add_argument("--output", type=Path, default=Path("build/hp1000/parity"))
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    commands = ["set on", "on error exit 1"]
    cases = []

    def begin(name):
        cases.append(name)
        commands.extend(["set cpu 1000-L", "reset", "deposit P 100"])

    def step(instruction, deposits, expected):
        commands.extend(f"deposit {a} {v}" for a, v in deposits.items())
        commands.extend([f"deposit 100 {instruction}", "on error ignore", "step", "on error exit 1"])
        commands.extend(f"assert {a}={v}" for a, v in expected.items())

    for even in [0, 1]:
        for op in ["SFS", "SFC"]:
            for suffix in ["", ",C"]:
                name = f"{op}_{even}_{suffix or 'hold'}"
                begin(name)
                skip = even == (op == "SFS")
                step(f"{op} 5{suffix}", {"LPAREVEN": str(even)},
                     {"P": "102" if skip else "101", "LPAREVEN": "0" if suffix else str(even)})
                commands.append(f"echo PARITY_PASS_{name}")
    for op in ["LIA", "LIB", "MIA", "MIB"]:
        begin(op)
        reg = "B" if op.endswith("B") else "A"
        step(f"{op} 5", {reg: "2", "LPAR": "100201"},
             {reg: "100203" if op.startswith("MI") else "100201"})
        commands.append(f"echo PARITY_PASS_{op}")
    for op in ["STC", "CLC"]:
        begin(op)
        step(f"{op} 5,C", {"LPAREN": "0" if op == "STC" else "1", "LPAREVEN": "1" if op == "STC" else "0"},
             {"LPAREN": "1" if op == "STC" else "0", "LPAREVEN": "0"})
        commands.append(f"echo PARITY_PASS_{op}")

    for fetch in [False, True]:
        name = "bad_fetch_suppressed" if fetch else "bad_data_loaded"
        begin(name)
        # Make a bad-parity RAM word using real instructions, then restore odd
        # sense before enabling detection. The trap cell calls our test handler.
        setup = {"5": "JSB 300", "301": "HLT 77", "201": "070202" if fetch else "12345",
                 "202": "54321", "100": "STF 5", "101": "LDA 201", "102": "STA 200",
                 "103": "CLF 5", "104": "STC 5", "105": "JMP 200" if fetch else "LDB 200",
                 "106": "HLT 1", "INTSYS": "0", "LINT23": "0"}
        commands.extend(f"deposit {a} {v}" for a, v in setup.items())
        commands.extend(["on error ignore", "run 100", "on error exit 1",
                         "assert P=302", "assert T=102077", "assert CIR=5", "assert LPAREN=0",
                         "assert LPFAULT=1", f"assert LPFETCH={int(fetch)}",
                         f"assert LPAR={'100200' if fetch else '200'}",
                         f"assert 300={'201' if fetch else '106'}", "assert 202=54321"])
        if not fetch:
            commands.append("assert B=12345")
        commands.append(f"echo PARITY_PASS_{name}")

    begin("disabled_then_enabled")
    setup = {"5": "JSB 300", "301": "HLT 77", "201": "12345", "100": "STF 5",
             "101": "LDA 201", "102": "STA 200", "103": "CLF 5", "104": "NOP",
             "105": "LDB 200", "106": "HLT 1", "107": "STC 5", "110": "LDA 200"}
    commands.extend(f"deposit {a} {v}" for a, v in setup.items())
    commands.extend(["on error ignore", "run 100", "on error exit 1", "assert P=107",
                     "assert T=102001", "assert LPFAULT=0", "assert B=12345",
                     "on error ignore", "go 107", "on error exit 1", "assert P=302",
                     "assert T=102077", "assert LPFAULT=1", "assert LPAR=200",
                     "echo PARITY_PASS_disabled_then_enabled"])
    begin("valid_odd_data")
    commands.extend(["deposit 100 STC 5", "deposit 101 LDB 200", "deposit 102 HLT 77",
                     "deposit 200 12345", "on error ignore", "run 100", "on error exit 1",
                     "assert P=103", "assert B=12345", "assert LPFAULT=0",
                     "echo PARITY_PASS_valid_odd_data"])
    commands.extend(["echo HP1000_CHECK_PASS", "exit"])
    script = args.output / "parity.ini"
    script.write_text("\n".join(commands) + "\n")
    result = execute(args.simulator.resolve(), script, script.with_suffix(".log"), 30)
    log = script.with_suffix(".log").read_text() if script.with_suffix(".log").exists() else ""
    passed = [name for name in cases if f"PARITY_PASS_{name}\n" in log]
    if result["status"] == "PASS" and passed != cases:
        result["status"] = "FAIL"
    result.update(planned=len(cases), executed=len(passed), cases=passed)
    (args.output / "results.json").write_text(json.dumps(result, indent=2) + "\n")
    print(f"{result['status']}: {len(passed)}/{len(cases)} independent parity checks")
    return int(result["status"] != "PASS")


if __name__ == "__main__":
    raise SystemExit(main())
