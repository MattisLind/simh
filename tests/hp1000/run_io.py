"""Independent standard-L processor-I/O checks from 02103-90007 tables 3-5/4-3.

No interface cards, DMA, memory-protection enforcement or VCP are claimed.
"""
import argparse
import json
from pathlib import Path
from run_baseline import execute


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--simulator', type=Path, default=Path('BIN/hp2100'))
    parser.add_argument('--output', type=Path, default=Path('build/hp1000/io'))
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    commands = ['set on', 'on error exit 1', 'set cpu 1000-L', 'set cpu 32K']
    cases = []

    def check(name, setup, run, expected):
        cases.append(name)
        commands.extend(['set cpu 1000-L', 'reset -p', 'deposit A 0', 'deposit B 0',
                         'deposit E 0', 'deposit O 0', 'deposit INTSYS 0',
                         'deposit LROMEN 0', 'deposit P 100'] + setup)
        for command in run:
            if command.startswith('step'):
                commands.extend(['on error ignore', command, 'on error exit 1'])
            else:
                commands.append(command)
        commands.extend(f'assert {a}={v}' for a, v in expected.items())
        commands.append(f'echo L_IO_PASS_{name}')

    def case(name, instruction, setup, expected):
        check(name, setup, [f'deposit 100 {instruction}', 'step'], expected)

    for reg, suffix in [('A', 'A'), ('B', 'B')]:
        case(f'mask_write_{reg}', f'OT{suffix} 0', [f'deposit {reg} 177777'], {'LIMASK': '2'})
        case(f'mask_load_{reg}', f'LI{suffix} 0', ['deposit LIMASK 2', f'deposit {reg} 177777'], {reg: '2'})
        case(f'mask_merge_{reg}', f'MI{suffix} 0', ['deposit LIMASK 2', f'deposit {reg} 100001'], {reg: '100003'})
        case(f'status_{reg}', f'LI{suffix} 1', ['deposit S 177777', 'deposit LIMASK 2'], {reg: '137400'})
        case(f'violation_write_{reg}', f'OT{suffix} 7,C', [f'deposit {reg} 177777', 'deposit LFENCE 123'], {'LVIO': '77777', 'LFENCE': '123'})
        case(f'fence_write_{reg}', f'OT{suffix} 7', [f'deposit {reg} 177777', 'deposit LVIO 321'], {'LFENCE': '77777', 'LVIO': '321'})
        case(f'violation_load_{reg}', f'LI{suffix} 7,C', ['deposit LVIO 12345'], {reg: '12345'})
        case(f'violation_merge_{reg}', f'MI{suffix} 7,C', ['deposit LVIO 12345', f'deposit {reg} 100000'], {reg: '112345'})
        case(f'violation_no_clear_nop_{reg}', f'LI{suffix} 7', [f'deposit {reg} 777', 'deposit LVIO 12345'], {reg: '777'})
        case(f'global_write_{reg}', f'OT{suffix} 2', [f'deposit {reg} 12345', 'deposit LGRDIS 1'], {'LGR': '45', 'LGRDIS': '1'})
        case(f'global_load_{reg}', f'LI{suffix} 2', ['deposit LGR 45'], {reg: '45'})
        for op in ('LI', 'MI', 'OT'):
            case(f'tbg_transfer_nop_{op}{suffix}', f'{op}{suffix} 6',
                 [f'deposit {reg} 12345', 'deposit LTBGFL 1'], {reg: '12345', 'LTBGFL': '1'})
    for reg, suffix in [('A', 'A'), ('B', 'B')]:
        for modifier, selected, other in [('', 'LPSAVE', 'LROMP'), (',C', 'LROMP', 'LPSAVE')]:
            for pattern in ('0', '125252', '177777'):
                case(f'SC3_write_{reg}_{selected}_{pattern}', f'OT{suffix} 3{modifier}',
                     [f'deposit {reg} {pattern}', f'deposit {other} 54321'],
                     {selected: pattern, other: '54321', reg: pattern, 'P': '101'})
            case(f'SC3_load_{reg}_{selected}', f'LI{suffix} 3{modifier}',
                 [f'deposit {selected} 125252', f'deposit {other} 54321'],
                 {reg: '125252', other: '54321', selected: '125252'})
            case(f'SC3_merge_{reg}_{selected}', f'MI{suffix} 3{modifier}',
                 [f'deposit {selected} 100002', f'deposit {reg} 1'],
                 {reg: '100003', selected: '100002'})
    for op in ('STF', 'CLF', 'SFS', 'SFC', 'STC'):
        case(f'SC3_NOP_{op}', f'{op} 3', ['deposit LROMP 125252', 'deposit LPSAVE 54321'],
             {'LROMP': '125252', 'LPSAVE': '54321', 'P': '101'})
    check('SC3_round_trip', ['deposit A 125252', 'deposit B 54321',
          'deposit E 1', 'deposit O 1', 'deposit 100 OTA 3,C', 'deposit 101 OTB 3',
          'deposit 102 LIA 3', 'deposit 103 LIB 3,C'], ['step 4'],
          {'A': '54321', 'B': '125252', 'LROMP': '125252', 'LPSAVE': '54321',
           'E': '1', 'O': '1', 'P': '104'})
    check('SC3_power_reset', ['deposit LROMP 125252', 'deposit LPSAVE 54321'],
          ['reset -p'], {'LROMP': '0', 'LPSAVE': '0'})
    # Provisional unassigned bus input; cover both A/B and hold/clear forms.
    for sc in (0o10, 0o11, 0o17, 0o20, 0o77):
        for op in ('LIA', 'LIB', 'MIA', 'MIB'):
            for modifier in ('', ',C'):
                reg = op[-1]
                other = 'B' if reg == 'A' else 'A'
                case(f'unassigned_{sc:o}_{op}_{modifier or "hold"}', f'{op} {sc:o}{modifier}',
                     [f'deposit {reg} 12345', f'deposit {other} 54321', 'deposit LVIO 14270'],
                     {reg: '177777', other: '54321', 'LVIO': '14270', 'P': '101'})
    for sc, flag in [(2, 'LGRDIS'), (6, 'LTBGFL')]:
        for value in (0, 1):
            for op in ('SFS', 'SFC'):
                skip = value == (op == 'SFS')
                case(f'flag_{sc}_{value}_{op}', f'{op} {sc},C', [f'deposit {flag} {value}'],
                     {'P': '102' if skip else '101', flag: '0'})
            case(f'set_{sc}_{value}', f'{"STF" if value else "CLF"} {sc}', [], {flag: str(value)})
    case('CLC6_clears_request', 'CLC 6', ['deposit LTBGEN 1', 'deposit LTBGFL 1'], {'LTBGEN': '0', 'LTBGFL': '0'})
    case('CRS_resets_TBG', 'CLC 0', ['deposit LTBGEN 1', 'deposit LTBGFL 1', 'deposit LTBGPHS 123', 'deposit LINT23 1', 'deposit LIMASK 2'], {'LTBGEN': '0', 'LTBGFL': '0', 'LTBGPHS': '72', 'LINT23': '1', 'LIMASK': '0'})
    # Gating tests use a software-set request with timer generation disabled.
    for name, setup in [('master', ['deposit INTSYS 0']),
                        ('type23', ['deposit INTSYS 1', 'deposit LINT23 0']),
                        ('mask', ['deposit INTSYS 1', 'deposit LIMASK 2'])]:
        case(f'irq_gate_{name}', 'NOP', ['deposit LTBGFL 1', 'deposit INTEN 1'] + setup,
             {'P': '101', 'LTBGFL': '1'})
    check('IRQ_defer_return', ['deposit LTBGFL 1', 'deposit 6 JSB 300',
          'deposit 100 STF 0', 'deposit 101 ISZ 200', 'deposit 200 0'],
          ['step 3'], {'P': '301', '200': '1', '300': '102', 'CIR': '6', 'LTBGFL': '0'})
    check('UI_unconditional', ['deposit 100 105100', 'deposit 10 JSB 300',
          'deposit LINT23 0', 'deposit A 123', 'deposit B 456', 'deposit E 1', 'deposit O 1'],
          ['step 2'], {'P': '301', '300': '101', 'CIR': '10', 'A': '123', 'B': '456', 'E': '1', 'O': '1'})
    # TBT+ comes from the CPU chip's divider even while SC6 gates requests.
    # CRS resets the functional phase, then its own 3.6us execution advances it.
    check('timer_disabled_divider_runs', ['deposit LTBGEN 0', 'deposit LTBGFL 0',
          'deposit LTBGPHS 199950', 'deposit 100 NOP'], ['step'],
          {'LTBGEN': '0', 'LTBGFL': '0', 'LTBGPHS': '14'})
    # NOP takes 3.2 us: the 3125th NOP crosses exactly 10 ms.
    setup = [f'deposit {a:o} NOP' for a in range(0o100, 0o100 + 3125)]
    setup += ['deposit LTBGEN 1', 'deposit LTBGPHS 0']
    check('timer_10ms', setup, ['step 3124', 'assert LTBGTIK=0', 'assert LTBGFL=0', 'step'],
          {'LTBGTIK': '1', 'LTBGFL': '1', 'LTBGPHS': '0'})
    commands += ['echo HP1000_CHECK_PASS', 'exit']
    script = args.output / 'processor-io.ini'
    script.write_text('\n'.join(commands) + '\n')
    log_path = script.with_suffix('.log')
    result = execute(args.simulator.resolve(), script, log_path, 30)
    log = log_path.read_text()
    executed = [n for n in cases if f'L_IO_PASS_{n}\n' in log]
    if executed != cases:
        result['status'] = 'FAIL'
    result.update(planned=len(cases), executed=len(executed), cases=executed)
    (args.output / 'results.json').write_text(json.dumps(result, indent=2) + '\n')
    print(f"{result['status']}: {len(executed)}/{len(cases)} processor-I/O checks")
    return int(result['status'] != 'PASS')


if __name__ == '__main__':
    raise SystemExit(main())
