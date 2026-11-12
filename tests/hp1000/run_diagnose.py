"""Mode-1 instruction checks for the actual empty L-Series backplane.

Synthetic populated-chip priority tests live in test_l_diagnose.c. No synthetic
card is installed into the simulator to make KERN appear to pass.
"""
import argparse
import json
from pathlib import Path
from run_baseline import execute


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--simulator', type=Path, default=Path('BIN/hp2100'))
    parser.add_argument('--output', type=Path, default=Path('build/hp1000/diagnose'))
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    commands = ['set on', 'on error exit 1', 'set cpu 1000-L', 'set cpu 32K']
    tests = []
    enter = ['deposit A 1', 'deposit 200 OTA 2', 'deposit P 200',
             'on error ignore', 'step', 'on error exit 1',
             'assert LDIAG1=1', 'deposit A 12345', 'deposit B 54321']

    def case(name, instruction, setup, expected):
        tests.append(name)
        commands.extend(['set cpu 1000-L', 'reset -p', 'deposit LGR 45',
                         'deposit A 12345', 'deposit B 54321', 'deposit E 1', 'deposit O 1'] + setup)
        commands.extend([f'deposit 100 {instruction}', 'deposit P 100',
                         'on error ignore', 'step', 'on error exit 1'])
        commands.extend(f'assert {a}={v}' for a, v in expected.items())
        commands.extend(['assert E=1', 'assert O=1', f'echo L_DIAG_PASS_{name}'])

    for reg in ('A', 'B'):
        for modifier in ('', ',C'):
            case(f'enter_{reg}_{modifier or "hold"}', f'OT{reg} 2{modifier}', [f'deposit {reg} 1'],
                 {'LDIAG1': '1', 'LGR': '45', reg: '1', 'LGRDIS': '0' if modifier else '1', 'P': '101'})
    for sc in (2, 0o20, 0o77):
        for reg in ('A', 'B'):
            for value in ('0', '125252', '177777'):
                for modifier in ('', ',C'):
                    case(f'empty_{sc:o}_{reg}_{value}_{modifier or "hold"}', f'LI{reg} {sc:o}{modifier}',
                         enter + [f'deposit {reg} {value}'],
                         {reg: value, 'LDIAG1': '1', 'LGR': '45', 'P': '101'})
    case('repeat', 'OTA 2', enter + ['deposit A 1'], {'LDIAG1': '1', 'LGR': '45'})
    case('terminate', 'OTA 2', enter + ['deposit A 0'], {'LDIAG1': '0', 'LGR': '45'})
    case('CRS', 'CLC 0', enter, {'LDIAG1': '0', 'LGR': '45'})
    case('STC0_NOP', 'STC 0', enter, {'LDIAG1': '1', 'LGR': '45'})
    case('GR_flag_independent', 'CLF 2', enter, {'LDIAG1': '1', 'LGRDIS': '0', 'LGR': '45'})
    case('global_change', 'OTA 2', enter + ['deposit A 70'], {'LDIAG1': '1', 'LGR': '70'})
    case('normal_empty_input', 'LIA 20', [], {'A': '177777', 'LDIAG1': '0'})
    # The new interfacing manuals specify the other mode commands and merge reads.
    for mode in range(2, 8):
        case(f'mode_command_{mode}', 'OTA 2', enter + [f'deposit A {mode}'],
             {'P': '101', 'LDIAG1': '1' if mode == 2 else '0', 'LDIAG': str(mode), 'LGR': '45', 'A': str(mode)})
    for sc in (2, 0o20):
        for reg in ('A', 'B'):
            case(f'empty_merge_{sc:o}_{reg}', f'MI{reg} {sc:o}', enter,
                 {'P': '101', 'A': '12345', 'B': '54321', 'LDIAG1': '1'})
    commands.extend(['reset -p', 'assert LDIAG1=0', 'echo HP1000_CHECK_PASS', 'exit'])
    script = args.output / 'mode1.ini'
    script.write_text('\n'.join(commands) + '\n')
    log_path = script.with_suffix('.log')
    result = execute(args.simulator.resolve(), script, log_path, 30)
    log = log_path.read_text()
    done = [n for n in tests if f'L_DIAG_PASS_{n}\n' in log]
    if done != tests:
        result['status'] = 'FAIL'
    result.update(planned=len(tests), executed=len(done), cases=done,
                  actual_L_cards=0, full_KERN_pass=False)
    (args.output / 'results.json').write_text(json.dumps(result, indent=2) + '\n')
    print(f"{result['status']}: {len(done)}/{len(tests)} diagnose instruction checks")
    return int(result['status'] != 'PASS')


if __name__ == '__main__':
    raise SystemExit(main())
