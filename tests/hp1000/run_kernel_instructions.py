"""Run unchanged KERN instruction tests directly from octal 03777.

Stops at diagnostic error handlers, an unsupported instruction, or TST05.
A successful harness run is distinct from a completed diagnostic.
"""
import argparse
import hashlib
import json
from pathlib import Path

from absolute_binary import inspect
from firmware_source import resolve
from run_baseline import execute


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--simulator', type=Path, default=Path('BIN/hp2100'))
    parser.add_argument('--output', type=Path, default=Path('build/hp1000/kernel-instructions-verified'))
    args = parser.parse_args()
    source = Path('hp1000-references/software/diagnostics/archives/type-4/24397-18002_Rev-2001.src')
    image = Path('hp1000-references/software/diagnostics/archives/type-7/24397-16002_Rev-2001.abin')
    _, memory = inspect(image)
    symbols, _ = resolve(source.read_text())
    if symbols['TST01'] != 0o3777 or memory[0o3777] != 0o60537:
        raise ValueError('unexpected KERN entry signature')
    args.output.mkdir(parents=True, exist_ok=True)
    commands = ['set on', 'on error exit 1', 'set cpu 1000-L', 'set cpu 32K', 'reset']
    commands += [f'deposit {a:o} {v:o}' for a, v in sorted(memory.items())]
    commands += [f'assert {a:o}={v:o}' for a, v in sorted(memory.items())]
    errors = {symbols[n] + 1 for n in ('CPERR', 'PRERR', 'MERR', 'DSPLY')}
    commands += [f'break {a:o}' for a in sorted(errors)]
    commands += ['deposit P 3777']
    # Each checkpoint must be reached in source control-flow order. Removing
    # its breakpoint permits execution of that instruction on the next step.
    for name in ('TST02', 'TST03', 'TST04', 'TSTJL', 'TST05'):
        address = symbols[name]
        commands += [f'break {address:o}', 'on error ignore', 'step 100000000',
                     'on error exit 1', 'examine P,A,B,E,O,IR',
                     f'assert P={address:o}', f'echo KERN_REACHED_{name}',
                     f'nobreak {address:o}']
    commands += ['echo HP1000_CHECK_PASS', 'exit']
    script = args.output / 'instructions.ini'
    script.write_text('\n'.join(commands) + '\n')
    log_path = args.output / 'instructions.log'
    run = execute(args.simulator.resolve(), script, log_path, 30)
    log = log_path.read_text()
    reached = [n for n in ('TST02', 'TST03', 'TST04', 'TSTJL', 'TST05')
               if f'KERN_REACHED_{n}\n' in log]
    status = ('PASS' if 'TST05' in reached else 'NOT_IMPLEMENTED'
              if 'L-Series feature not yet emulated' in log else run['status'])
    result = {'instruction_phase': status, 'full_KERN_pass': False,
              'entry_octal': '03777', 'reached': reached, 'execution': run,
              'source_sha256': hashlib.sha256(source.read_bytes()).hexdigest(),
              'image_sha256': hashlib.sha256(image.read_bytes()).hexdigest()}
    (args.output / 'results.json').write_text(json.dumps(result, indent=2) + '\n')
    print(json.dumps(result, indent=2))
    return 0 if status in ('PASS', 'NOT_IMPLEMENTED') else 1


if __name__ == '__main__':
    raise SystemExit(main())
