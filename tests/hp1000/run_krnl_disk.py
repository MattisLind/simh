"""Run unchanged KRNL from 24397A.hpi through original VCP, with failure stops.

Requires genuine memory/instruction entry and all I/O tests to complete. Reaching
an error handler is a failed diagnostic, even if earlier prefix tests pass.
"""
import argparse
import hashlib
import json
import re
from pathlib import Path
from absolute_binary import inspect as absolute
from firmware import read_pair
from firmware_source import resolve
from rte_disk import inspect
from run_baseline import execute


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--simulator', type=Path, default=Path('BIN/hp2100'))
    parser.add_argument('--output', type=Path, default=Path('build/hp1000/krnl-disk'))
    parser.add_argument('--second-asi', action='store_true', help='also validate ASI1 at SC21')
    args = parser.parse_args()
    out = args.output
    out.mkdir(parents=True, exist_ok=True)
    root = Path('hp1000-references/software/diagnostics/archives')
    source = root / 'type-4/24397-18002_Rev-2001.src'
    symbols, _ = resolve(source.read_text())
    image = root / '24397A.hpi'
    data = image.read_bytes()
    original_hash = hashlib.sha256(data).hexdigest()
    entry = next(e for e in inspect(image)['files'] if e['name'] == 'KRNL')
    kernel = data[entry['offset']:entry['offset'] + entry['bytes']]
    _, memory = absolute(root / 'type-7/24397-16002_Rev-2001.abin')
    if any(int.from_bytes(kernel[a*2:a*2+2], 'big') != word for a, word in memory.items()):
        raise ValueError('disk KRNL does not match original Rev.2001 absolute/source')
    words, _ = read_pair(root / 'type-4/12001-16001_Rev-2140.src', root / 'type-4/12001-16002_Rev-2150.src')
    rom = out / 'rom.bin'
    rom.write_bytes(b''.join(w.to_bytes(2, 'big') for w in words))
    commands = ['set on', 'on error exit 1', 'set cpu 1000-L', 'set ASI enabled',
                'set HPI enabled', f'set cpu LROM={rom.resolve()}',
                f'attach -r HPI0 {image.resolve()}', f'attach ASI {(out / "console.txt").resolve()}',
                'deposit S 400', 'reset -p', 'on error ignore', 'step 50000000',
                'on error exit 1', 'assert LSTATUS=207', f'break {symbols["TST05"]:o}',
                'send "\\045BDC27KRNL\\r"', 'on error ignore', 'step 100000000',
                'on error exit 1', f'assert P={symbols["TST05"]:o}',
                'echo KRNL_MEMORY_AND_CPU_PHASES_COMPLETE', f'nobreak {symbols["TST05"]:o}']
    if args.second_asi:
        commands.insert(5, 'set ASI1 enabled')
    # Protection probes execute temporary JMPs at diagnostic code addresses.
    # Accept CHIPS only after its original instruction has been restored.
    commands.append(f'break {symbols["CHIPS"]:o}')
    for _ in range(8):
        commands.extend(['on error ignore', 'step 100000000', 'on error exit 1',
                         f'if {symbols["CHIPS"]:o}={memory[symbols["CHIPS"]]:o} goto chips_ready'])
    commands.extend(['exit AFAIL', ':chips_ready', f'assert P={symbols["CHIPS"]:o}',
                     'echo KRNL_PROCESSOR_IO_AND_PROTECTION_COMPLETE',
                     f'nobreak {symbols["CHIPS"]:o}'])
    # All handler addresses now contain their original diagnostic routines.
    for label in ['CPERR', 'PRERR', 'MERR', 'IOERR']:
        commands.append(f'break {symbols[label] + 1:o}')
    commands.append(f'break {symbols["HLT14"]:o}')
    commands.extend([f'break {symbols["TST08"]:o}', 'on error ignore', 'step 100000000',
                     'on error exit 1', 'ex P,A,B,CIR,LDIAG,LGR,LGRDIS,LSTATUS',
                     f'ex {symbols["IOERR"]:o}', f'assert P={symbols["TST08"]:o}',
                     'echo KRNL_NON_DMA_IO_COMPLETE', f'nobreak {symbols["TST08"]:o}'])
    commands.extend([f'break {symbols["TST09"]:o}', 'on error ignore', 'step 100000000',
                     'on error exit 1', 'ex P,A,B,CIR,LDIAG,LGR,LGRDIS,LSTATUS',
                     f'ex {symbols["IOERR"]:o}', 'ex 410-430', 'ex 472-510',
                     f'assert P={symbols["TST09"]:o}', 'echo KRNL_ALL_TESTS_COMPLETE',
                     'on error ignore', 'step 2', 'on error exit 1',
                     'assert LSTATUS=177777', 'ex LSTATUS', 'echo HP1000_CHECK_PASS', 'exit'])
    script = out / 'krnl.ini'
    script.write_text('\n'.join(commands) + '\n')
    run = execute(args.simulator.resolve(), script, script.with_suffix('.log'), 180)
    transcript = script.with_suffix('.log').read_text(errors='replace')
    state = dict(re.findall(r'^(P|A|B|CIR|LDIAG|LGR|LGRDIS|LSTATUS):\s*([0-7]+)$', transcript, re.M))
    unchanged = hashlib.sha256(image.read_bytes()).hexdigest() == original_hash
    passed = run['status'] == 'PASS' and unchanged and 'KRNL_ALL_TESTS_COMPLETE' in transcript
    result = dict(full_KRNL_pass=passed, second_ASI=args.second_asi, non_DMA_IO_pass='KRNL_NON_DMA_IO_COMPLETE' in transcript,
                  original_disk_unchanged=unchanged,
                  disk_sha256=original_hash, KRNL_sha256=entry['sha256'],
                  matches_original_absolute_words=len(memory), state=state, execution=run,
                  expected_completion=f'{symbols["TST09"]:05o}',
                  source=str(source), software_patched=False)
    (out / 'results.json').write_text(json.dumps(result, indent=2) + '\n')
    print(json.dumps(result, indent=2))
    return int(not passed)


if __name__ == '__main__':
    raise SystemExit(main())
