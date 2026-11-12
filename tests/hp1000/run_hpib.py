"""Execute the unmodified disk HPIB against the 12009A and the original read-only diagnostic disk.

A full pass requires the original diagnostic to report PASS COMPLETE without
an error. A prefix, instruction-budget expiry, or timing stall is not a pass.
"""
import argparse
import hashlib
import json
from pathlib import Path
from firmware import read_pair
from rte_disk import inspect
from run_baseline import execute


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--simulator', type=Path, default=Path('BIN/hp2100'))
    parser.add_argument('--output', type=Path, default=Path('build/hp1000/hpib-disk'))
    parser.add_argument('--instructions', type=int, default=30_000_000)
    args = parser.parse_args()
    out = args.output
    out.mkdir(parents=True, exist_ok=True)
    root = Path('hp1000-references/software/diagnostics/archives')
    disk = root / '24397A.hpi'
    original_hash = hashlib.sha256(disk.read_bytes()).hexdigest()
    entry = next(e for e in inspect(disk)['files'] if e['name'] == 'HPIB')
    words, _ = read_pair(root / 'type-4/12001-16001_Rev-2140.src',
                         root / 'type-4/12001-16002_Rev-2150.src')
    rom = out / 'rom.bin'
    rom.write_bytes(b''.join(w.to_bytes(2, 'big') for w in words))
    console = out / 'console.txt'
    console.write_bytes(b'')
    commands = ['set on', 'on error exit 1', 'set cpu 1000-L', 'set ASI enabled',
                'set HPI enabled',
                f'set cpu LROM={rom.resolve()}', f'attach -r HPI0 {disk.resolve()}',
                f'attach ASI {console.resolve()}', 'deposit S 400', 'reset -p',
                'on error ignore', 'step 50000000', 'on error exit 1', 'assert LSTATUS=207']
    for text, count in [('\\045BDC27HPIB\\r', 30000000), ('RU\\r', 10000000),
                        ('27\\r', args.instructions)]:
        commands += [f'send "{text}"', 'on error ignore', f'step {count}', 'on error exit 1']
    commands += ['ex P,A,B,CIR,INTSYS,INTEN,LTBGEN,LTBGFL,LTBGTIK',
                 'ex HPI CONTROL,STATUS,FLAGS,CONTROLS,DMAEN,INCOUNT,OUTCOUNT',
                 'ex HPI PHI[0-7]', 'ex HPI REGS[16-31]', 'ex 275-306',
                 'echo HP1000_CHECK_PASS', 'exit']
    script = out / 'hpib.ini'
    script.write_text('\n'.join(commands) + '\n')
    run = execute(args.simulator.resolve(), script, script.with_suffix('.log'), 240)
    text = console.read_text(errors='replace')
    unchanged = hashlib.sha256(disk.read_bytes()).hexdigest() == original_hash
    card_pass = (run['status'] == 'PASS' and unchanged and 'ERROR' not in text
                 and ' STOP' not in text and 'PASS COMPLETE' in text)
    disk_loopback = card_pass and 'DISC CONTROLLER LOOPBACK TEST' in text
    passed = card_pass and disk_loopback and 'NO HP-IB DISCS FOUND' not in text
    result = dict(full_HPIB_pass=passed, interface_checks_pass=card_pass,
                  disk_loopback_pass=disk_loopback, two_card_test_run=False, software_patched=False,
                  original_disk_unchanged=unchanged, disk_sha256=original_hash,
                  HPIB_sha256=entry['sha256'], execution=run,
                  console=str(console))
    (out / 'results.json').write_text(json.dumps(result, indent=2) + '\n')
    print(json.dumps(result, indent=2))
    return int(not passed)


if __name__ == '__main__':
    raise SystemExit(main())
