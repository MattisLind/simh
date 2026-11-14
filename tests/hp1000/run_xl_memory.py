"""Directed 12002A CPU translation and cross-map instruction regressions.

The larger original HP diagnostic is run separately by run_xl_diagnostic.py.
"""
import argparse
import json
from pathlib import Path
from run_baseline import execute


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--simulator', type=Path, default=Path('BIN/hp2100'))
    parser.add_argument('--output', type=Path, default=Path('build/hp1000/xl-memory'))
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    script = Path('tests/hp1000/config/xl-memory.ini')
    result = execute(args.simulator.resolve(), script, args.output / 'translation.log', 30)
    result['coverage'] = ['JMP-delayed map enable', 'CPU map translation',
        'XLD alternate A/current B', 'XST alternate A/inhibited B',
        'logical writes preserve shadow map', 'CLC13 physical override']
    (args.output / 'results.json').write_text(json.dumps(result, indent=2) + '\n')
    print(json.dumps(result, indent=2))
    return int(result['status'] != 'PASS')


if __name__ == '__main__':
    raise SystemExit(main())
