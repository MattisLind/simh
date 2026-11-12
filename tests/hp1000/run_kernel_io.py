"""Compare unchanged KERN processor-I/O entry at octal 13777 with entry 03777.

The verified prefix ends at memory-protection tests; full KERN is not passed.
"""
import argparse
import hashlib
import json
import re
from pathlib import Path

from absolute_binary import inspect
from firmware_source import resolve
from run_baseline import execute


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--simulator', type=Path, default=Path('BIN/hp2100'))
    parser.add_argument('--output', type=Path, default=Path('build/hp1000/kernel-io-verified'))
    args = parser.parse_args()
    source = Path('hp1000-references/software/diagnostics/archives/type-4/24397-18002_Rev-2001.src')
    image = Path('hp1000-references/software/diagnostics/archives/type-7/24397-16002_Rev-2001.abin')
    _, memory = inspect(image)
    symbols, _ = resolve(source.read_text())
    expected = {'TST05': 0o13777, 'TBTST': 0o14063, 'JSBTR': 0o14151,
                'UITST': 0o14200, 'MPTST': 0o14234, 'STC5': 0o14246, 'MPT03': 0o14324}
    if any(symbols[n] != a for n, a in expected.items()):
        raise ValueError('unexpected KERN Rev.2001 source layout')
    if memory[0o13777] != 0o107700 or memory[0o14246] != 0o102707:
        raise ValueError('unexpected binary boundary signatures')
    args.output.mkdir(parents=True, exist_ok=True)
    runs = []
    checkpoints = [('REGISTERS', symbols['TST05'] + 4)] + [
        (n, symbols[n]) for n in ('TBTST', 'JSBTR', 'UITST', 'MPTST', 'MPT03')]
    for entry in (0o13777, 0o3777):
        commands = ['set on', 'on error exit 1', 'set cpu 1000-L', 'set cpu 32K', 'reset']
        commands += [f'deposit {a:o} {v:o}' for a, v in sorted(memory.items())]
        commands += [f'assert {a:o}={v:o}' for a, v in sorted(memory.items())]
        errors = {symbols[n] + 1 for n in ('CPERR', 'PRERR', 'MERR', 'DSPLY', 'ILINT')}
        commands += [f'break {a:o}' for a in sorted(errors)]
        commands += [f'deposit P {entry:o}']
        for name, address in checkpoints:
            commands += [f'break {address:o}', 'on error ignore', 'step 100000000',
                         'on error exit 1', f'assert P={address:o}',
                         f'echo KERN_IO_REACHED_{name}', f'nobreak {address:o}']
        commands += [f'assert {symbols["TEMP7"]:o}=20', 'echo KERN_UI_16_TRAPS_PASS',
                     'examine P,A,B,E,O,IR,CIR,LIMASK,LTBGEN,LTBGFL,LTBGTIK,LFENCE,LVIO,LMPEN,LMPFLT',
                     'examine 17665', 'assert LROMP=0', 'assert LPSAVE=0', 'assert P=14324', 'assert LMPFLT=2',
                     f'assert LVIO={symbols["TH003"]:o}', 'assert LMPEN=0',
                     'assert 17665=0', 'echo KERN_IO_PREFIX_PASS',
                     'echo HP1000_CHECK_PASS', 'exit']
        script = args.output / f'entry-{entry:05o}.ini'
        script.write_text('\n'.join(commands) + '\n')
        log_path = script.with_suffix('.log')
        run = execute(args.simulator.resolve(), script, log_path, 30)
        log = log_path.read_text()
        state = dict(re.findall(r'^(P|A|B|E|O|IR|CIR|LIMASK|LTBGEN|LTBGFL|LTBGTIK|LFENCE|LVIO|LMPEN|LMPFLT):\s*([0-9]+)$', log, re.M))
        reached = [n for n, _ in checkpoints if f'KERN_IO_REACHED_{n}\n' in log]
        passed = (run['status'] == 'PASS' and len(reached) == len(checkpoints)
                  and 'KERN_UI_16_TRAPS_PASS\n' in log and 'KERN_IO_PREFIX_PASS\n' in log)
        runs.append({'entry_octal': f'{entry:05o}', 'prefix': 'PASS' if passed else 'FAIL',
                     'reached': reached, 'final_state': state, 'execution': run})
    same = runs[0]['final_state'] == runs[1]['final_state'] and bool(runs[0]['final_state'])
    passed = same and all(r['prefix'] == 'PASS' for r in runs)
    result = {'processor_io_prefix': 'PASS' if passed else 'FAIL',
              'entry_comparison': 'MATCH' if same else 'MISMATCH',
              'full_KERN_pass': False, 'memory_protection': 'INITIAL_HLT_AND_IO_CHECKS_PASS',
              'next_stop': '14324: MPT03 checkpoint; select-code sweep complete', 'runs': runs,
              'source_sha256': hashlib.sha256(source.read_bytes()).hexdigest(),
              'image_sha256': hashlib.sha256(image.read_bytes()).hexdigest()}
    (args.output / 'results.json').write_text(json.dumps(result, indent=2) + '\n')
    print(json.dumps(result, indent=2))
    return 0 if passed else 1


if __name__ == '__main__':
    raise SystemExit(main())
