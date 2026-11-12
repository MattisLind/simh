"""Execute the unmodified disk ASIC against ASI1 and a virtual test hood.

A full pass requires the diagnostic to return to its select-code prompt without
an error. A prefix, instruction-budget expiry, or timing stall is not a pass.
"""
import argparse
import hashlib
import json
from pathlib import Path
from firmware import read_pair
from rte_disk import inspect, append_files
from absolute_binary import inspect as absolute
from run_baseline import execute


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--simulator', type=Path, default=Path('BIN/hp2100'))
    parser.add_argument('--output', type=Path)
    parser.add_argument('--revision', choices=['2001', '2040'], default='2001')
    parser.add_argument('--instructions', type=int, default=120_000_000)
    args = parser.parse_args()
    out = args.output or Path('build/hp1000/asic-disk' + ('-rev2040' if args.revision == '2040' else ''))
    out.mkdir(parents=True, exist_ok=True)
    root = Path('hp1000-references/software/diagnostics/archives')
    disk = root / '24397A.hpi'
    original_hash = hashlib.sha256(disk.read_bytes()).hexdigest()
    entry = next(e for e in inspect(disk)['files'] if e['name'] == 'ASIC')
    boot_disk, filename = disk, 'ASIC'
    original_entry = entry
    binary_sha = None
    if args.revision == '2040':
        info, memory = absolute(root / 'type-7/24397-16005_Rev-2040.abin')
        binary_sha = info['sha256']
        if max(memory) >= 0o76000:
            raise ValueError('diagnostic overlaps the original loader workspace')
        payload = b''.join(memory.get(a, 0).to_bytes(2, 'big') for a in range(max(memory) + 1))
        payload += bytes((-len(payload)) % 256)
        boot_disk, filename = out / 'diag-asic2040.hpi', 'ASIC40'
        directory = append_files(disk, boot_disk, [(filename, 1, payload)])
        entry = next(e for e in directory['files'] if e['name'] == filename)
        # Verify HP's documented PINT fix against the actual original binary.
        if (memory[0o11672], memory[0o11725], memory[0o11726]) != (0o027725, 0o102100, 0o127660):
            raise ValueError('unexpected Rev.2040 interrupt-restore path')
    words, _ = read_pair(root / 'type-4/12001-16001_Rev-2140.src',
                         root / 'type-4/12001-16002_Rev-2150.src')
    rom = out / 'rom.bin'
    rom.write_bytes(b''.join(w.to_bytes(2, 'big') for w in words))
    console = out / 'console.txt'
    console.write_bytes(b'')
    commands = ['set on', 'on error exit 1', 'set cpu 1000-L', 'set ASI enabled',
                'set ASI1 enabled', 'set ASI1 HOOD', 'set HPI enabled',
                f'set cpu LROM={rom.resolve()}', f'attach -r HPI0 {boot_disk.resolve()}',
                f'attach ASI {console.resolve()}', 'deposit S 400', 'reset -p',
                'on error ignore', 'step 50000000', 'on error exit 1', 'assert LSTATUS=207']
    for text, count in [(f'\\045BDC27{filename}\\r', 30000000), ('RU\\r', 10000000),
                        ('21\\r', 10000000), ('YES\\r', args.instructions)]:
        commands += [f'send "{text}"', 'on error ignore', f'step {count}', 'on error exit 1']
    commands += ['ex P,A,B,CIR,INTSYS,INTEN,LTBGEN,LTBGFL,LTBGTIK',
                 'ex ASI1 CONTROL,STATUS,FLAGS,CONTROLS,DMAEN,TXWAIT',
                 'echo HP1000_CHECK_PASS', 'exit']
    script = out / 'asic.ini'
    script.write_text('\n'.join(commands) + '\n')
    run = execute(args.simulator.resolve(), script, script.with_suffix('.log'), 240)
    text = console.read_text(errors='replace')
    unchanged = hashlib.sha256(disk.read_bytes()).hexdigest() == original_hash
    baud_tests = [line.strip() for line in text.splitlines()
                  if 'BAUD RATE UNDER TEST' in line]
    passed = (len(baud_tests) >= 15 and run['status'] == 'PASS' and unchanged and 'ERROR' not in text
              and ' STOP' not in text and 'PASS COMPLETE' in text
              and 'EXTERNAL CLOCK SOURCE TEST' in text and text.count('INPUT SELECT CODE') >= 2)
    result = dict(full_ASIC_pass=passed, revision=args.revision, software_patched=False,
                  original_ASIC_sha256=original_entry['sha256'], absolute_binary_sha256=binary_sha,
                  boot_disk=str(boot_disk),
                  original_disk_ASIC_pass=(passed and args.revision == '2001'),
                  original_disk_unchanged=unchanged, disk_sha256=original_hash,
                  ASIC_sha256=entry['sha256'], execution=run,
                  baud_tests_started=baud_tests,
                  virtual_hood_wiring='24612-90011 table 2-1 / figure 2-1; 12005-90001 figure 7-4',
                  console=str(console))
    (out / 'results.json').write_text(json.dumps(result, indent=2) + '\n')
    print(json.dumps(result, indent=2))
    return int(not passed)


if __name__ == '__main__':
    raise SystemExit(main())
