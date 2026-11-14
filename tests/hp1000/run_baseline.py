"""Bounded HP2100 regressions and original L-series image load verification.

No L-series instructions are executed: the existing 1000-E model checks
deposits and independently loads the image through its paper-tape ROM loader.
"""
import argparse
import json
import subprocess
from pathlib import Path

from absolute_binary import inspect

MODELS = ("2116", "2115", "2114", "2100", "1000-M", "1000-E", "1000-F")


def execute(simulator, script, output, timeout):
    try:
        result = subprocess.run([str(simulator), str(script.resolve())],
                                input="", text=True, errors="replace", stdout=subprocess.PIPE,
                                stderr=subprocess.STDOUT, timeout=timeout)
        output.write_text(result.stdout)
        passed = result.returncode == 0 and "HP1000_CHECK_PASS" in result.stdout
        return {"status": "PASS" if passed else "FAIL",
                "returncode": result.returncode, "log": str(output)}
    except subprocess.TimeoutExpired as exc:
        captured = exc.stdout or b""
        output.write_text(captured.decode(errors="replace")
                          if isinstance(captured, bytes) else captured)
        return {"status": "TIMEOUT", "log": str(output)}
    except OSError as exc:
        return {"status": "BLOCKED", "reason": str(exc)}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--simulator", type=Path, default=Path("BIN/hp2100"))
    parser.add_argument("--output", type=Path, default=Path("build/hp1000"))
    parser.add_argument("--timeout", type=float, default=30)
    parser.add_argument("--image", type=Path, default=Path(
        "hp1000-references/software/diagnostics/archives/type-7/"
        "24397-16002_Rev-2001.abin"))
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    results = []
    for model in MODELS:
        script = args.output / f"baseline-{model}.ini"
        script.write_text(f"""set on
on error exit 1
set cpu {model}
reset
deposit 100 LDA 110
deposit 101 ADA 111
deposit 102 STA 112
deposit 103 HLT 77
deposit 110 1234
deposit 111 1
on error ignore
run 100
on error exit 1
assert P=104
assert T=102077
assert A=1235
assert 112=1235
echo HP1000_CHECK_PASS
exit
""")
        result = execute(args.simulator.resolve(), script,
                         script.with_suffix(".log"), args.timeout)
        results.append({"test": "load/add/store", "model": model, **result})
    if args.image.exists():
        try:
            info, memory = inspect(args.image)
            script = args.output / "kernel-load.ini"
            # Address zero/one alias A/B in the existing simulator. The
            # deposit/assert sequence checks the image representation only.
            script.write_text("set on\non error exit 1\n"
                              "set cpu 1000-E\nset cpu 32K\nreset\n" +
                              "".join(f"deposit {a:o} {v:o}\n"
                                      for a, v in sorted(memory.items())) +
                              "".join(f"assert {a:o}={v:o}\n"
                                      for a, v in sorted(memory.items())) +
                              "echo HP1000_CHECK_PASS\nexit\n")
            result = execute(args.simulator.resolve(), script,
                             script.with_suffix(".log"), args.timeout)
            results.append({"test": "original-kernel-load-only", "model": "1000-E",
                            "image": str(args.image), "sha256": info["sha256"],
                            "records": len(info["records"]), "words": len(memory),
                            "diagnostic_tests_executed": 0, **result})
            script = args.output / "kernel-ptr-load.ini"
            # This independent load path executes the existing 12992K loader,
            # not our generated deposits or the L diagnostic. A/B (addresses
            # 0/1) are loader scratch registers and cannot retain image words.
            expected = {a: v for a, v in memory.items() if a > 1}
            script.write_text("set on\non error exit 1\n"
                              "set cpu 1000-E\nset cpu 32K\nreset\n"
                              f"attach -r ptr {json.dumps(str(args.image.resolve()))}\n"
                              "on error ignore\nboot ptr\non error exit 1\n"
                              "assert T=102077\nassert P=77712\n" +
                              "".join(f"assert {a:o}={v:o}\n"
                                      for a, v in sorted(expected.items())) +
                              "echo HP1000_CHECK_PASS\nexit\n")
            result = execute(args.simulator.resolve(), script,
                             script.with_suffix(".log"), args.timeout)
            results.append({"test": "original-kernel-PTR-load-only", "model": "1000-E",
                            "words_checked": len(expected), "excluded_addresses": [0, 1],
                            "diagnostic_tests_executed": 0, **result})
        except (OSError, ValueError) as exc:
            results.append({"test": "original-kernel-load-only", "status": "FAIL",
                            "reason": str(exc)})
    else:
        results.append({"test": "original-kernel-load-only", "status": "BLOCKED",
                        "reason": "original reference image unavailable"})
    results.append({"test": "L-series-kernel-execution", "model": "L-series",
                    "status": "NOT_IMPLEMENTED", "diagnostic_tests_executed": 0})
    (args.output / "results.json").write_text(json.dumps(results, indent=2) + "\n")
    for result in results:
        print(result["status"], result.get("model", ""), result["test"])
    return int(any(r["status"] in ("FAIL", "TIMEOUT", "UNKNOWN", "BLOCKED")
                   for r in results))


if __name__ == "__main__":
    raise SystemExit(main())
