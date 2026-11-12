"""Verify ROM routing and bounded original firmware startup; report unfinished gates.

Requires the private HP references for original startup. Synthetic routing tests
are separate from authentic firmware/pretest evidence. This runner does not
pretend that reaching an unfinished processor I/O operation is full startup.
"""
import argparse
import json
import subprocess
import sys
from pathlib import Path

from firmware import read_pair
from run_baseline import execute


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--simulator", type=Path, default=Path("BIN/hp2100"))
    parser.add_argument("--root", type=Path, default=Path(
        "hp1000-references/software/diagnostics/archives/type-4"))
    parser.add_argument("--output", type=Path, default=Path("build/hp1000/firmware"))
    parser.add_argument("--require-vcp", action="store_true",
                        help="run and require authentic pretest and interactive VCP checks")
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    results = []

    def run(name, commands):
        script = args.output / f"{name}.ini"
        script.write_text("set on\non error exit 1\nset cpu 1000-L\n" +
                          "\n".join(commands) + "\necho HP1000_CHECK_PASS\nexit\n")
        result = execute(args.simulator.resolve(), script, script.with_suffix(".log"), 30)
        result["test"] = name
        results.append(result)
        return result

    image = [0] * 4096
    for page in range(4):
        base = page * 1024
        for offset, value in {0o100: 0o60200, 0o101: 0o64200, 0o102: 0o70201,
                              0o103: 0o64201, 0o105: 0o60001,
                              0o106: 0o160210, 0o107: 0o164210,
                              0o110: 0o100200, 0o111: 0o200,
                              0o112: 0o102702, 0o113: 0o6400,
                              0o114: 0o100600, 0o115: 0o100210,
                              0o116: 0o104600, 0o117: 0o100210,
                              0o200: 0x1100 + page, 0o210: 0o220,
                              0o220: 0x1200 + page}.items():
            image[base + offset] = value
    synthetic = args.output / "synthetic ROM.bin"
    synthetic.write_bytes(b"".join(w.to_bytes(2, "big") for w in image))
    commands = [f"set cpu LROM={json.dumps(str(synthetic.resolve()))}",
                "deposit LROMEN 1", "deposit 200 75432", "deposit 210 221", "deposit 221 12345"]

    def step(address, expected, setup=()):
        commands.extend(setup)
        commands.extend([f"deposit P {address:o}", "on error ignore", "step", "on error exit 1"])
        commands.extend(f"assert {a}={v:o}" for a, v in expected.items())

    for page in range(4):
        commands.extend([f"deposit LSTATUS {page * 128:o}", "deposit LROMEN 1"])
        marker = 0x1100 + page
        # JL* uses ROM for EAU inline operands and indirect pointers,
        # including JLB despite its B selector (unlike B-side MRG reads).
        step(0o114, {"A": 0o116, "P": 0o220})
        step(0o116, {"B": 0o120, "P": 0o220})
        step(0o100, {"A": marker, "P": 0o101})
        step(0o101, {"B": 0o75432})
        step(0o102, {"201": marker})
        step(0o103, {"B": marker})
        step(0o105, {"A": 0o54321}, ["deposit B 54321"])
        step(0o106, {"A": 0x1200 + page})
        step(0o107, {"B": 0o12345})
        step(0o110, {"A": marker * 2, "B": 0, "P": 0o112}, ["deposit A 2"])
        # STC 2 leaves the following ROM exit instruction executable.
        step(0o112, {"LROMEN": 1, "LROMDLY": 1})
        step(0o113, {"B": 0, "LROMEN": 0}, ["deposit B 123"])
        step(0o114, {"B": 0, "P": 0o115})  # RAM NOP, not ROM JLA.
        # Select a page via actual OTB 1 while fetching from RAM.
        commands.extend(["deposit 300 OTB 1", f"deposit B {page * 128:o}",
                         f"deposit LSTATUS {((page + 1) % 4) * 128:o}"])
        step(0o300, {"LSTATUS": page * 128, "P": 0o301})
        commands.append(f"echo ROM_PAGE_PASS_{page}")
    commands.extend(["deposit LSTATUS 0", "deposit LROMEN 1"])
    step(0o76100, {"A": 0x1100, "P": 0o76101})
    # A failed image replacement must not damage the previously installed image.
    invalid = args.output / "short.bin"
    invalid.write_bytes(b"\0" * 8191)
    commands.extend(["on FMT goto bad_image", f"set cpu LROM={invalid.resolve()}", "exit 1",
                     ":bad_image", "on FMT exit 1", "assert LROMLD=1",
                     "deposit LROMEN 1", "deposit LSTATUS 0"])
    step(0o100, {"A": 0x1100})
    # Model isolation: M/E/F ignores a retained processor ROM image.
    commands.extend(["set cpu 1000-E", "deposit 100 LDA 200", "deposit 200 321"])
    step(0o100, {"A": 0o321})
    run("rom-routing", commands)

    try:
        words, lanes = read_pair(args.root / "12001-16001_Rev-2140.src",
                                 args.root / "12001-16002_Rev-2150.src")
        authentic = args.output / "processor-rom.bin"
        authentic.write_bytes(b"".join(w.to_bytes(2, "big") for w in words))
        trace = args.output / "power-on.trace"
        trace.write_text("")  # SIMH appends debug output; each result needs its own trace.
        result = run("authentic-startup", [
            f"set cpu LROM={authentic.resolve()}", "reset -p", "assert P=2",
            "assert LROMEN=1", "assert LSTATUS=0", f"set debug {trace.resolve()}",
            "set cpu debug=instr;data;reg", "break 425", "on error ignore", "step 5000",
            "on error exit 1", "assert P=425", "nobreak 425",
            "on error ignore", "step", "on error exit 1", "assert P=426", "assert IR=107607",
            "set nodebug"])
        result.update(scope="original CPU instruction pretest reaches processor-card I/O",
                      lanes=lanes, trace=str(trace), stop="checked prefix through OTB 7,C; boundary 00426 / source 04426",
                      complete_power_on_pretest=False)
        trace_text = trace.read_text() if trace.exists() else ""
        instructions = [line for line in trace_text.splitlines()
                        if line.startswith(">>CPU instr:") and "simulation stop:" not in line]
        result["instruction_attempts"] = len(instructions)
        if result["status"] == "PASS" and (len(instructions) != 164
                or "00002  024100" not in instructions[0]
                or "00425  107607" not in instructions[-1]):
            result["status"] = "FAIL"
        boot = run("authentic-boot-cpu", [
            f"set cpu LROM={authentic.resolve()}", "break 426", "on error ignore",
            "boot CPU", "on error exit 1", "assert P=426", "assert IR=107607", "nobreak 426"])
        boot["complete_power_on_pretest"] = False
        # The universal L/XL PROM probes absent mapping controls. Standard L
        # now treats those controls as no-ops and reaches the I/O test entry.
        if words[0o1054] != 0o102601:
            raise ValueError("unexpected original I/O-pretest boundary")
        extended = run("authentic-pretest-probe", [
            f"set cpu LROM={authentic.resolve()}", "reset -p", "nobreak all",
            "break 77054", "on error ignore", "step 20000000", "on error exit 1",
            "assert P=77054", "assert LROMEN=1", "nobreak 77054"])
        extended.update(complete_power_on_pretest=False,
                        stop="I/O-pretest entry 77054; no L interface installed in this runner")
    except (OSError, ValueError) as exc:
        results.append({"test": "authentic-startup", "status": "BLOCKED", "reason": str(exc)})

    gates = ["complete-power-on-pretest", "interactive-VCP", "12005A-console",
             "VCP-slave-mode-single-step"]
    gate_status = "NOT_RUN"
    if args.require_vcp:
        target = args.output / "12005a"
        with (args.output / "12005a.log").open("w") as log:
            completed = subprocess.run([
                sys.executable, str(Path(__file__).with_name("run_asi.py")),
                "--simulator", str(args.simulator), "--root", str(args.root),
                "--output", str(target)], stdout=log, stderr=subprocess.STDOUT,
                timeout=180)
        gate_status = "PASS" if completed.returncode == 0 else "FAIL"
    for name in gates:
        results.append({"test": name, "status": gate_status,
                        "runner": "run_asi.py"})
    results.append({"test": "VCP-diagnostic-bootstrap", "status": "NOT_RUN", "runner": "run_hpi.py"})
    (args.output / "firmware-results.json").write_text(json.dumps(results, indent=2) + "\n")
    for result in results:
        print(result["status"], result["test"])
    return int(any(r["status"] in ["FAIL", "TIMEOUT", "BLOCKED"] for r in results))


if __name__ == "__main__":
    raise SystemExit(main())
