"""Verify original KERN MPT09 after complete startup; no diagnostic patches.

A source-signature check distinguishes the PRIPR checkpoint from temporary
relocated test code at the same address. Full KERN completion is not claimed.
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
    parser.add_argument('--asi', action='store_true', help='verify enumeration with the real 12005A enabled')
    parser.add_argument('--output', type=Path, default=Path('build/hp1000/kernel-indirect'))
    args = parser.parse_args()
    source = Path('hp1000-references/software/diagnostics/archives/type-4/24397-18002_Rev-2001.src')
    image = Path('hp1000-references/software/diagnostics/archives/type-7/24397-16002_Rev-2001.abin')
    _, memory = inspect(image)
    symbols, _ = resolve(source.read_text())
    if symbols['PRIPR'] != 0o15140 or symbols['MPT09'] != 0o15053:
        raise ValueError('unexpected source layout')
    args.output.mkdir(parents=True, exist_ok=True)
    commands = ['set on', 'on error exit 1', 'set cpu 1000-L', 'set cpu 32K', 'reset -p']
    if args.asi:
        commands.insert(3, 'set ASI enabled')
    commands += [f'deposit {a:o} {v:o}' for a, v in sorted(memory.items())]
    commands += [f'assert {a:o}={v:o}' for a, v in sorted(memory.items())]
    commands += ['break 3777', 'deposit P 2', 'on error ignore', 'step 50000000',
                 'on error exit 1', 'assert P=3777', 'assert LPFAULT=513', 'assert LPFETCH=1',
                 'assert 525=77777', 'echo KERN_STARTUP_PASS', 'nobreak all']
    # These error entries lie below the relocating test interval (MPT08 onward).
    commands += [f'break {symbols[n]+1:o}' for n in ('CPERR', 'DSPLY', 'MERR', 'ILINT')]
    target = symbols['PRIPR']
    commands += [f'break {target:o}', ':probe', 'on error ignore', 'step 100000000',
                 'on error exit 1', f'if P!={target:o} goto failed',
                 f'if {target:o}={memory[target]:o} goto reached',
                 # Skip a temporary test-module instruction under the breakpoint.
                 f'nobreak {target:o}', 'on error ignore', 'step', 'on error exit 1',
                 f'break {target:o}', 'goto probe', ':reached', f'nobreak {target:o}',
                 f'assert {symbols["EXITM"]:o}={symbols["EXILP"]:o}',
                 f'assert {symbols["EXITN"]:o}={symbols["EXILQ"]:o}',
                 'assert 13635=0', 'echo KERN_MPT09_PASS',
                 f'break {symbols["IOERR"]+1:o}',
                 *([f'break {symbols["TST06"]:o}'] if args.asi else []),
                 'on error ignore', 'step 1000000', 'on error exit 1',
                 'examine P,A,B,E,O,IR,CIR,LVIO,LFENCE,LMPFLT',
                 *([f'assert P={symbols["TST06"]:o}',
                    f'assert {symbols["SCTBL"]+1:o}=20', f'assert {symbols["SCTBL"]+2:o}=0',
                    'echo KERN_MODE1_12005A_CONFIRMED'] if args.asi else
                   [f'assert P={symbols["IOERR"]+1:o}',
                    f'assert {symbols["IOERR"]:o}={symbols["NOSC"]+3:o}',
                    f'assert {symbols["SCTBL"]+1:o}=0', 'assert A=0', 'assert LDIAG1=1',
                    'echo KERN_MODE1_EMPTY_BUS_CONFIRMED']),
                 'echo HP1000_CHECK_PASS', 'exit', ':failed',
                 'examine P,A,B,E,O,IR', 'examine 13635', 'exit 1']
    script = args.output / 'kernel-indirect.ini'
    script.write_text('\n'.join(commands) + '\n')
    log_path = script.with_suffix('.log')
    run = execute(args.simulator.resolve(), script, log_path, 30)
    log = log_path.read_text()
    passed = run['status'] == 'PASS' and 'KERN_MPT09_PASS\n' in log
    result = {'MPT09': 'PASS' if passed else 'FAIL', 'full_KERN_pass': False,
              'diagnose_mode_1': '12005A_ENUMERATED' if args.asi else 'EMPTY_BUS_CONFIRMED',
              'KERN_IO_diagnostic': 'TST06_ENTRY_REACHED' if args.asi else 'NO_IO_CHIPS_RESPONDED',
              'next_stop': 'TST06 checkpoint' if args.asi else 'IOERR: original NOSC no-I/O-chips check', 'execution': run,
              'source_sha256': hashlib.sha256(source.read_bytes()).hexdigest(),
              'image_sha256': hashlib.sha256(image.read_bytes()).hexdigest()}
    (args.output / 'results.json').write_text(json.dumps(result, indent=2) + '\n')
    print(json.dumps(result, indent=2))
    return int(not passed)


if __name__ == '__main__':
    raise SystemExit(main())
