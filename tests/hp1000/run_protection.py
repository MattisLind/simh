"""Independent standard-L memory protection checks: 02103-90007 section 4-3.

The original diagnostic prefix is checked separately by run_kernel_io.py.
"""
import argparse
import json
from pathlib import Path
from run_baseline import execute


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--simulator', type=Path, default=Path('BIN/hp2100'))
    parser.add_argument('--output', type=Path, default=Path('build/hp1000/protection'))
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    commands = ['set on', 'on error exit 1', 'set cpu 1000-L', 'set cpu 32K']
    cases = []

    def case(name, instruction, setup, expected, count=1, address=0o100):
        cases.append(name)
        commands.extend(['set cpu 1000-L', 'reset -p', 'deposit LROMEN 0',
                         'deposit A 12345', 'deposit B 54321', 'deposit E 1', 'deposit O 1',
                         'deposit INTSYS 0', 'deposit 7 JSB 300', 'deposit 300 0',
                         f'deposit {address:o} ' + instruction, 'deposit 200 777',
                         f'deposit P {address:o}'] + setup + ['on error ignore', f'step {count}', 'on error exit 1'])
        commands.extend(f'assert {a}={v}' for a, v in expected.items())
        commands.append(f'echo L_MP_PASS_{name}')

    for op in ('STA', 'STB', 'ISZ', 'JSB', 'JMP'):
        case(f'{op}_below', f'{op} 200', ['deposit LFENCE 201', 'deposit LMPEN 1'],
             {'200': '777', 'LVIO': '100', 'LMPIRQ': '1', 'LMPFLT': '1',
              'P': '201' if op == 'JSB' else '200' if op == 'JMP' else '101', 'E': '1', 'O': '1'})
    for op, result in [('STA', '12345'), ('STB', '54321'), ('ISZ', '1000'), ('JSB', '101')]:
        case(f'{op}_at_fence', f'{op} 200', ['deposit LFENCE 200', 'deposit LMPEN 1'],
             {'200': result, 'LMPIRQ': '0', 'LMPFLT': '0'})
    case('JMP_at_fence', 'JMP 200', ['deposit LFENCE 200', 'deposit LMPEN 1'],
         {'P': '200', 'LMPIRQ': '0'})
    for op in ('STA', 'STB', 'ISZ', 'JSB'):
        case(f'{op}_alias', f'{op} 1', ['deposit LFENCE 77777', 'deposit LMPEN 1'],
             {'LMPIRQ': '0', 'LMPFLT': '0'})
    for address in (0, 1):
        case(f'JMP_alias_{address}', f'JMP {address}', ['deposit LFENCE 0', 'deposit LMPEN 1'],
             {'P': str(address), 'LVIO': '100', 'LMPIRQ': '1'})
    for op in ('LDA', 'LDB', 'ADA', 'ADB', 'AND', 'IOR', 'XOR', 'CPA', 'CPB'):
        case(f'{op}_read_allowed', f'{op} 200', ['deposit LFENCE 77777', 'deposit LMPEN 1'],
             {'200': '777', 'LMPIRQ': '0', 'LMPFLT': '0'})
    case('indirect_through_protected', 'STA 200,I',
         ['deposit 200 300', 'deposit 300 777', 'deposit LFENCE 300', 'deposit LMPEN 1'],
         {'200': '300', '300': '12345', 'LMPIRQ': '0'})
    case('indirect_into_protected', 'STA 300,I',
         ['deposit 300 200', 'deposit LFENCE 300', 'deposit LMPEN 1'],
         {'200': '777', '300': '200', 'LVIO': '100', 'LMPIRQ': '1'})
    case('DST_below', 'DST 200', ['deposit 201 123', 'deposit LFENCE 201', 'deposit LMPEN 1'],
         {'200': '777', '201': '123', 'LVIO': '100', 'LMPIRQ': '1'})
    case('DST_at_fence', 'DST 200', ['deposit LFENCE 200', 'deposit LMPEN 1'],
         {'200': '12345', '201': '54321', 'LMPIRQ': '0'})
    for instruction in ('HLT 3', 'HLT 1', '103001', 'LIA 4', 'STF 6', 'CLC 0,C', 'OTA 7'):
        case('IO_' + instruction.replace(' ', '_'), instruction,
             ['deposit LFENCE 0', 'deposit LMPEN 1', 'deposit LTBGFL 0'],
             {'A': '12345', 'B': '54321', 'E': '1', 'O': '1', 'LVIO': '100',
              'LMPIRQ': '1', 'LFENCE': '0', 'LTBGFL': '0'})
    for instruction in ('LIA 1', 'LIB 1', 'CLO', 'STC 1', 'CLC 1'):
        case('SC1_' + instruction.replace(' ', '_'), instruction, ['deposit LMPEN 1'],
             {'LMPEN': '1', 'LMPIRQ': '0'})
    case('enable', 'STC 7', [], {'LMPEN': '1', 'LMPIRQ': '0'})
    case('CLC7_is_NOP', 'CLC 7', [], {'LMPEN': '0', 'LMPIRQ': '0'})
    case('disabled_store', 'STA 200', ['deposit LFENCE 77777'], {'200': '12345', 'LMPIRQ': '0'})
    case('Type2_ignores_master', 'STA 200', ['deposit LFENCE 201', 'deposit LMPEN 1'],
         {'P': '301', '300': '101', 'CIR': '7', 'LMPEN': '0', 'LMPIRQ': '0'}, count=2)
    case('Type2_SC4_gated', 'STA 200', ['deposit LFENCE 201', 'deposit LMPEN 1', 'deposit LINT23 0', 'deposit 101 NOP'],
         {'P': '102', '300': '0', 'LMPEN': '1', 'LMPIRQ': '1'}, count=2)
    case('IO_trap_preserves_MP', 'NOP', ['deposit LMPEN 1', 'deposit INTSYS 1',
         'deposit LTBGFL 1', 'deposit INTEN 1', 'deposit 6 CLF 6'],
         {'P': '100', 'CIR': '6', 'LMPEN': '1', 'LTBGFL': '0'})
    for bit in range(2, 15):
        fence = 1 << bit
        for below in (True, False):
            target = fence - int(below)
            case(f'fence_bit_{bit}_{"below" if below else "at"}', 'STA 700,I',
                 [f'deposit LFENCE {fence:o}', 'deposit LMPEN 1',
                  f'deposit 700 {target:o}', f'deposit {target:o} 777'],
                 {f'{target:o}': '777' if below else '12345',
                  'LMPIRQ': '1' if below else '0'}, address=0o77000)
    commands.extend(['echo HP1000_CHECK_PASS', 'exit'])
    script = args.output / 'protection.ini'
    script.write_text('\n'.join(commands) + '\n')
    log_path = script.with_suffix('.log')
    result = execute(args.simulator.resolve(), script, log_path, 30)
    log = log_path.read_text()
    done = [n for n in cases if f'L_MP_PASS_{n}\n' in log]
    if done != cases:
        result['status'] = 'FAIL'
    result.update(planned=len(cases), executed=len(done), cases=done)
    (args.output / 'results.json').write_text(json.dumps(result, indent=2) + '\n')
    print(f"{result['status']}: {len(done)}/{len(cases)} protection checks")
    return int(result['status'] != 'PASS')


if __name__ == '__main__':
    raise SystemExit(main())
