"""Run the unchanged HP 12002A/B XL diagnostic through original VCP/BOOTX."""
import argparse
import hashlib
import json
from pathlib import Path
from absolute_binary import inspect as absolute
from firmware import read_pair
from rte_disk import append_files
from run_baseline import execute


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--simulator', type=Path, default=Path('BIN/hp2100'))
    parser.add_argument('--memory', type=int, choices=[64, 128, 256], default=256)
    parser.add_argument('--output', type=Path)
    parser.add_argument('--instructions', type=int, default=2000000000)
    args = parser.parse_args()
    out = args.output or Path(f'build/hp1000/xl-diagnostic-{args.memory}k')
    out.mkdir(parents=True, exist_ok=True)
    root = Path('hp1000-references/software/diagnostics/archives')
    original = root / '24397A.hpi'
    binary = root / 'type-7/24397-16004_Rev-2040.abin'
    original_hash = hashlib.sha256(original.read_bytes()).hexdigest()
    info, memory = absolute(binary)
    payload = b''.join(memory.get(a, 0).to_bytes(2, 'big') for a in range(max(memory) + 1))
    payload += bytes(-len(payload) % 256)
    disk = out / 'xl-diagnostic.hpi'
    append_files(original, disk, [('XL40', 1, payload)])
    words, _ = read_pair(root / 'type-4/12001-16001_Rev-2140.src',
                         root / 'type-4/12001-16002_Rev-2150.src')
    rom = out / 'rom.bin'
    rom.write_bytes(b''.join(w.to_bytes(2, 'big') for w in words))
    console = out / 'console.txt'
    console.write_bytes(b'')
    c = ['set on', 'on error exit 1', f'set cpu 1000-L,{args.memory}K',
         'set ASI enabled', 'set ASI1 enabled', 'set HPI enabled',
         f'set cpu LROM={rom.resolve()}', f'attach -r HPI0 {disk.resolve()}',
         f'attach ASI {console.resolve()}', 'deposit S 400', 'reset -p',
         'on error ignore', 'step 50000000', 'on error exit 1', 'assert LSTATUS=207',
         'send "\\045BDC27XL40\\r"', 'on error ignore', 'step 30000000',
         'on error exit 1', 'expect "ERROR" goto failed',
         'expect "DIAGNOSTIC COMPLETE" goto completed', 'send "RU\\r"',
         'on error ignore', f'step {args.instructions}', 'on error exit 1',
         ':failed', 'ex P,A,B,LSTATUS,LMAPON,LMAPNEXT,LMAPSC5', 'exit AFAIL',
         ':completed', 'noexpect', 'echo HP1000_CHECK_PASS', 'exit']
    script = out / 'diagnostic.ini'
    script.write_text('\n'.join(c) + '\n')
    run = execute(args.simulator.resolve(), script, script.with_suffix('.log'), 900)
    text = console.read_text(errors='replace')
    phases = ['XST, XLD & MAP RAM TEST', 'MAP ENABLE TEST', 'MEMORY ADDRESS TEST',
              'MEMORY PATTERN TEST', 'WORST CASE PATTERN TEST', 'ADDRESS PARITY TEST',
              'DISTURBANCE TEST', 'PARITY GENERATOR TEST', 'DMA AND ADDRESS EXTENSION TEST',
              'LOGICAL - PHYSICAL', 'MAP RAM DATA & INTF. LATCH', 'ADDER TEST ON CONTROLLER']
    unchanged = hashlib.sha256(original.read_bytes()).hexdigest() == original_hash
    passed = (run['status'] == 'PASS' and 'DIAGNOSTIC COMPLETE' in text and 'ERROR' not in text
              and f'TOTAL MEMORY = {args.memory:3d}K WORDS' in text
              and all(phase in text for phase in phases) and unchanged)
    result = dict(status='PASS' if passed else 'FAIL', memory_KW=args.memory,
                  full_original_XL_diagnostic=passed, phases=phases,
                  installed_interfaces=['ASI SC20', 'HPI SC27', 'ASI1 SC21'],
                  original_disk_unchanged=unchanged, original_disk_sha256=original_hash,
                  diagnostic_sha256=info['sha256'], software_patched=False,
                  execution=run, console=str(console))
    (out / 'results.json').write_text(json.dumps(result, indent=2) + '\n')
    print(json.dumps(result, indent=2))
    return int(not passed)


if __name__ == '__main__':
    raise SystemExit(main())
