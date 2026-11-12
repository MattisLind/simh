"""L built-in indirect-chain interrupt recognition; reference section 4-7.

One/two-level indirect jumps defer through the following instruction. A pending
Type 3 request is enabled at level three; longer chains restart after service.
"""
import argparse
import json
from pathlib import Path
from run_baseline import execute


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--simulator', type=Path, default=Path('BIN/hp2100'))
    parser.add_argument('--output', type=Path, default=Path('build/hp1000/indirect'))
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    commands = ['set on', 'on error exit 1', 'set cpu 1000-L', 'set cpu 32K']
    tests = []

    def case(name, setup, expected, count=1, instruction='JMP 200,I'):
        tests.append(name)
        commands.extend(['set cpu 1000-L', 'reset -p', 'set cpu indir=16',
                         'deposit LROMEN 0', 'deposit A 12345', 'deposit B 54321',
                         'deposit E 1', 'deposit O 1', 'deposit INTSYS 1',
                         'deposit LTBGFL 1', 'deposit INTEN 0', 'deposit 6 JSB 400',
                         'deposit 400 0', 'deposit 300 777', 'deposit 100 ' + instruction,
                         'deposit P 100'] + setup + ['on error ignore', f'step {count}', 'on error exit 1'])
        expected = dict(A='12345', B='54321', E='1', O='1', **expected)
        commands.extend(f'assert {a}={v}' for a, v in expected.items())
        commands.append(f'echo L_INDIRECT_PASS_{name}')

    for levels in (1, 2, 3, 4, 5):
        setup = [f'deposit {0o200+i:o} {((0o100000 | (0o201+i)) if i < levels-1 else 0o300):o}' for i in range(levels)]
        case(f'levels_{levels}', setup,
             {'P': '100' if levels >= 4 else '300', 'INTEN': '1' if levels >= 3 else '0',
              'LTBGFL': '1', '400': '0'})
        if levels >= 3:
            case(f'return_{levels}', setup,
                 {'P': '401', 'CIR': '6', '400': '100' if levels >= 4 else '300', 'LTBGFL': '0'}, count=2)
    chain = ['deposit 200 100201', 'deposit 201 100202', 'deposit 202 100203', 'deposit 203 300']
    for name, gate in [('master', 'deposit INTSYS 0'), ('mask', 'deposit LIMASK 2'), ('type23', 'deposit LINT23 0')]:
        case('gate_' + name, chain + [gate], {'P': '300', 'INTEN': '0', '400': '0', 'LTBGFL': '1'})
    case('JSB_no_partial_store', chain,
         {'P': '100', '300': '777', '400': '0'}, instruction='JSB 200,I')
    case('MP_enable_not_required', chain + ['deposit LMPEN 0'], {'P': '401', 'CIR': '6', '400': '100'}, count=2)
    # Timer reaches 10 ms during resolution, not before the instruction starts.
    case('arrives_inside_loop', ['deposit 200 100200', 'deposit LTBGFL 0',
         'deposit LTBGEN 1', 'deposit LTBGPHS 199900'],
         {'P': '401', 'CIR': '6', '400': '100', 'LTBGTIK': '1'}, count=2)
    case('no_request_resolves', chain + ['deposit LTBGFL 0'], {'P': '300', '400': '0'})
    case('late_timer_inside_long_loop', ['deposit 200 100200', 'deposit LTBGFL 0',
         'deposit LTBGEN 1', 'deposit LTBGPHS 0', 'set cpu indir=32768'],
         {'P': '401', 'CIR': '6', '400': '100', 'LTBGTIK': '1'}, count=2)
    case('no_request_limit', ['deposit 200 100200', 'deposit LTBGFL 0'],
         {'P': '100', '400': '0', 'LTBGFL': '0'})
    # Preserve the original 2116 distinction: the installed board matters,
    # regardless of whether its protection fence is enabled.
    commands += ['set cpu 2116', 'set TBG SC=77', 'set TBG enabled']
    for installed in (True, False):
        name = '2116_MP_' + ('present' if installed else 'absent')
        tests.append(name)
        commands += [f'set MP {"enabled" if installed else "disabled"}', 'reset -p',
                     'deposit INTSYS 1', 'deposit INTEN 0', 'deposit TBG CTL 1',
                     'deposit TBG FLG 1', 'deposit TBG FBF 1',
                     'deposit 100 JMP 200,I', 'deposit 200 100201',
                     'deposit 201 100202', 'deposit 202 100203', 'deposit 203 300',
                     'deposit P 100', 'on error ignore', 'step', 'on error exit 1',
                     f'assert P={"100" if installed else "300"}',
                     f'assert INTEN={int(installed)}', f'echo L_INDIRECT_PASS_{name}']
    commands += ['echo HP1000_CHECK_PASS', 'exit']
    script = args.output / 'indirect.ini'
    script.write_text('\n'.join(commands) + '\n')
    log_path = script.with_suffix('.log')
    result = execute(args.simulator.resolve(), script, log_path, 30)
    log = log_path.read_text()
    done = [n for n in tests if f'L_INDIRECT_PASS_{n}\n' in log]
    if done != tests:
        result['status'] = 'FAIL'
    result.update(planned=len(tests), executed=len(done), cases=done)
    (args.output / 'results.json').write_text(json.dumps(result, indent=2) + '\n')
    print(f"{result['status']}: {len(done)}/{len(tests)} indirect interrupt checks")
    return int(result['status'] != 'PASS')


if __name__ == '__main__':
    raise SystemExit(main())
