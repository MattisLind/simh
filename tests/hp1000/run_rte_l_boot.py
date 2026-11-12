"""Boot the generated RTE-L SYSTEM with an HP2645 terminal peer and query TM.

ACK is sent only in response to ENQ. All banner, prompt and clock text must be
emitted by authentic HP execution; this runner never deposits guest memory.
The image remains read-only. An installed disk-based FMGR is not claimed.
"""
import argparse
import hashlib
import json
import re
from pathlib import Path
from firmware import read_pair
from rte_disk import inspect
from run_baseline import execute


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--simulator', type=Path, default=Path('BIN/hp2100'))
    parser.add_argument('--image', type=Path, default=Path('build/hp1000/rte-l-generated/rte-l-7902.hpi'))
    parser.add_argument('--output', type=Path, default=Path('build/hp1000/rte-l-boot'))
    parser.add_argument('--entry', type=lambda s: int(s, 8), default=0o2003)
    parser.add_argument('--banner-only', action='store_true')
    args = parser.parse_args()
    out = args.output
    out.mkdir(parents=True, exist_ok=True)
    raw = args.image.read_bytes()
    digest = hashlib.sha256(raw).hexdigest()
    directory = inspect(args.image)
    entry = next(e for e in directory['files'] if e['name'] == 'SYSTEM')
    system = raw[entry['offset']:entry['offset'] + entry['bytes']]
    if entry['type'] != 1 or len(system) != 65536:
        raise ValueError('expected the generated 32KW type-1 SYSTEM')
    root = Path('hp1000-references/software/diagnostics/archives/type-4')
    words, _ = read_pair(root / '12001-16001_Rev-2140.src', root / '12001-16002_Rev-2150.src')
    rom = out / 'rom.bin'
    rom.write_bytes(b''.join(w.to_bytes(2, 'big') for w in words))
    console = out / 'console.txt'
    console.write_bytes(b'')
    commands = ['set on', 'on error exit 1', 'set cpu 1000-L', 'set ASI enabled',
                'set HPI enabled', f'set cpu LROM={rom.resolve()}',
                f'attach -r HPI0 {args.image.resolve()}', f'attach ASI {console.resolve()}',
                'deposit S 400', 'reset -p', 'on error ignore', 'step 50000000',
                'on error exit 1', 'assert LSTATUS=207', f'break {args.entry:o}',
                'send "\\045BDC27\\r"', 'on error ignore', 'step 30000000',
                'on error exit 1', f'assert P={args.entry:o}', 'assert LROMEN=0']
    commands += [f'assert {a:o}={int.from_bytes(system[a*2:a*2+2], "big"):o}' for a in range(2, 0o76000)]
    commands += [f'nobreak {args.entry:o}',
                 'expect -p "\\005" send after=100,delay=100,"\\006"; goto wait_for_output']
    if args.banner_only:
        commands += ['expect "*RTE-L SYSTEM READY*" goto done']
    else:
        commands += ['expect "COMND:" goto first_prompt']
    commands += [':wait_for_output', 'on error ignore', 'step 5000000', 'on error exit 1', 'exit AFAIL']
    if not args.banner_only:
        commands += [':first_prompt',
                     r'expect -r "[0-9]+:[ ]*[0-9]+:[ ]*[0-9]+[^\r\n]*\r\n" goto done',
                     'send after=10000,delay=10000,"TM\\r"', 'goto wait_for_output']
    commands += [':done', 'noexpect']
    if not args.banner_only:
        # HP memory-based COMND deliberately terminates after one interactive
        # command (92070-18076 CALR). Verify return to the generated EXEC's idle
        # state ($XQT=0), rather than inventing a second-prompt requirement.
        commands += ['on error ignore', 'step 10000', 'on error exit 1', 'assert 2002=0']
    commands += ['ex P,A,B,CIR,LSTATUS,LROMEN,INTSYS,INTEN',
                 'echo HP1000_CHECK_PASS', 'exit']
    script = out / 'boot.ini'
    script.write_text('\n'.join(commands) + '\n')
    run = execute(args.simulator.resolve(), script, script.with_suffix('.log'), 120)
    text = console.read_text(errors='replace')
    unchanged = hashlib.sha256(args.image.read_bytes()).hexdigest() == digest
    ready = '*RTE-L SYSTEM READY*' in text
    tm = bool(re.search(r'\d{1,2}:\s*\d{1,2}:\s*\d{1,2}', text))
    commands_ok = 'COMND:' in text and tm and 'ABORTED' not in text
    passed = run['status'] == 'PASS' and unchanged and ready and (args.banner_only or commands_ok)
    result = dict(status='PASS' if passed else 'FAIL', execution=run,
                  kernel_ready=ready, command_prompt=('COMND:' in text), TM_completed=commands_ok,
                  SYSTEM_sha256=entry['sha256'], image_sha256=digest, image_unchanged=unchanged,
                  SYSTEM_words_compared=0o76000 - 2, terminal='HP2645 ENQ/ACK peer',
                  software_patched=False, disk_based_FMGR_installed=False, console=str(console))
    (out / 'results.json').write_text(json.dumps(result, indent=2) + '\n')
    print(json.dumps(result, indent=2))
    return int(not passed)


if __name__ == '__main__':
    raise SystemExit(main())
