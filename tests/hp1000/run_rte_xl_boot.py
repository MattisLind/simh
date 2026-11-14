"""Boot generated RTE-XL through unchanged HP VCP and XL BOOTEX on a 7902 or 7920.

Installs original libraries and HP-linked FMGR into a working FMP cartridge.
Driver parameter installation follows INSTL; all boot operations run in HP code.
"""
import argparse
import hashlib
import json
import re
from pathlib import Path
from firmware import read_pair
from rte_disk import inspect, pack_files
from rte_records import encode_text, decode_text
from rte_xl_boot import install_parameters
from run_baseline import execute


def payloads(image, model="7902"):
    if model == "7920":
        from software_media import fmp_files
        raw = bytearray(image.read_bytes())
        raw[::2], raw[1::2] = raw[1::2], raw[::2]
        return fmp_files(raw, 96, 405)
    raw = image.read_bytes()
    return {e['name']: (e['type'], raw[e['offset']:e['offset'] + e['bytes']])
            for e in inspect(image)['files']}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--simulator', type=Path, default=Path('BIN/hp2100'))
    parser.add_argument('--generated', type=Path, default=Path('build/hp1000/rte-xl-generated'))
    parser.add_argument('--programs', type=Path, default=Path('build/hp1000/rte-xl-programs'))
    parser.add_argument('--output', type=Path, default=Path('build/hp1000/rte-xl-7902'))
    parser.add_argument('--disk', choices=['7902', '7920'], default='7902')
    args = parser.parse_args()
    out = args.output
    out.mkdir(parents=True, exist_ok=True)
    master = Path('hp1000-references/software/operating-systems/92071_RTE-XL_MasterDiscs_Rev2340/92071-13401_RTE-XL-1_REV2340.hpi')
    original_hash = hashlib.sha256(master.read_bytes()).hexdigest()
    for directory in [args.generated, args.programs]:
        if json.loads((directory / 'results.json').read_text())['status'] != 'PASS':
            raise ValueError('generation and program-link validation must pass first')
    original = payloads(master)
    system = (args.generated / 'SYSTEM.bin').read_bytes()
    snapshot = (args.generated / 'SNAP.bin').read_bytes()
    boot, installer = install_parameters(original['BOOTEX'][1], system, snapshot, 2)
    fmgr = (args.programs / 'FMGR.bin').read_bytes()
    recorded = json.loads((args.programs / 'results.json').read_text())['programs']['FMGR']
    if hashlib.sha256(fmgr).hexdigest() != recorded['sha256']:
        raise ValueError('linked FMGR differs from validated build')
    directory_manager = (args.programs / 'D.RTR.bin').read_bytes()
    files = {n: f for n, f in original.items() if n.startswith('$')}
    text = 'RTE-XL FILE TEST\nPERSISTENT DISK DATA\n'
    files.update(BOOTEX=(1, boot), SYSTEM=(1, system), SNAP=(3, snapshot), FMGR=(6, fmgr), **{'D.RTR': (6, directory_manager)},
        BOOT=(3, encode_text('SY,SYSTEM\nSN,SNAP\nMC,2\nMS,4\nMS,24\nMS,21\nRP,D.RTR\nSZ,4\nRP,FMGR\nSZ,24\nST,1,1,1\nEN\n')),
        XLTEST=(3, encode_text(text)))
    if args.disk == '7920':
        from rte_7920 import make_image
        files['BOOT'] = (3, encode_text('SY,SYSTEM\nSN,SNAP\nMC,2\nMS,4\n' +
            'MS,32\n' * 7 + 'RP,D.RTR\nSZ,4\nRP,FMGR\nSZ,32\nST,1,1,1\nEN\n'))
        # A preallocated blank scratch file bounds swap below FMP's signed
        # sector-count limit on this larger volume. BOOTEX initializes it.
        files['SWAP'] = (1, bytes(2 * 1024 * 1024))
        disk = out / 'rte-xl-7920.disc'
        layout = make_image(disk, {0: files})
        (out / 'layout.json').write_text(json.dumps(layout, indent=2) + '\n')
        attachment = ['set HPI HARDDISK', 'set DA enabled', 'set DA0 7920',
                      f'attach DA0 {disk.resolve()}']
    else:
        disk = out / 'rte-xl-7902.hpi'
        pack_files(master, disk, files, 32001, first='BOOTEX')
        attachment = [f'attach HPI0 {disk.resolve()}']
    source = Path('hp1000-references/software/diagnostics/archives/type-4')
    words, _ = read_pair(source / '12001-16001_Rev-2140.src', source / '12001-16002_Rev-2150.src')
    rom = out / 'rom.bin'
    rom.write_bytes(b''.join(w.to_bytes(2, 'big') for w in words))
    def session(name, commands):
        console = out / (name + '-console.txt')
        console.write_bytes(b'')
        c = ['set on', 'on error exit 1', f'set cpu 1000-L,{256 if args.disk == "7920" else 64}K', 'set ASI enabled',
             'set HPI enabled', f'set cpu LROM={rom.resolve()}', *attachment,
             f'attach ASI {console.resolve()}', 'deposit S 400', 'reset -p',
             'on error ignore', 'step 50000000', 'on error exit 1', 'assert LSTATUS=207',
             r'expect -p "\005" send after=10000,delay=10000,"\006"; goto wait',
             'expect "FMGR : \\021" goto prompt0', r'send "\045BDC27BOOT\r"', ':wait',
             'on error ignore', 'step 200000000', 'on error exit 1', 'exit AFAIL']
        for i, command in enumerate(commands):
            c += [f':prompt{i}', f'expect "FMGR : \\021" goto prompt{i + 1}',
                  f'send after=10000,delay=10000,"{command}\\r"', 'goto wait']
        c += [f':prompt{len(commands)}', 'noexpect', 'assert LROMEN=0',
              'echo HP1000_CHECK_PASS', 'exit']
        script = out / (name + '.ini')
        script.write_text('\n'.join(c) + '\n')
        run = execute(args.simulator.resolve(), script, script.with_suffix('.log'), 600)
        terminal = console.read_text(errors='replace')
        passed = (run['status'] == 'PASS' and 'BOOT PROCESS COMPLETE' in terminal
                  and 'FMGR : ' in terminal and not re.search(r'ABORTED|FMP ERROR|ER 000|BAD PARAMETER|FMGR[- ]\d', terminal))
        if not passed:
            raise RuntimeError(f'{name} failed: inspect {console}')
        return run
    first = session('development', ['DL', 'ST,XLTEST,COPY,AS', 'DU,COPY,1'])
    stored = payloads(disk, args.disk)['COPY']
    if decode_text(stored[1]) != text:
        raise ValueError('native XL file copy did not preserve records')
    saved_hash = hashlib.sha256(stored[1]).hexdigest()
    second = session('reboot', ['DU,COPY,1', 'RN,COPY,RENAM', 'DU,RENAM,1'])
    if hashlib.sha256(payloads(disk, args.disk)['RENAM'][1]).hexdigest() != saved_hash:
        raise ValueError('XL file did not persist through fresh boot and rename')
    unchanged = hashlib.sha256(master.read_bytes()).hexdigest() == original_hash
    result = dict(status='PASS' if unchanged else 'FAIL', target_booted=True,
        disk=args.disk, memory_KW=256 if args.disk == '7920' else 64, logical_mapping=True, original_BOOTEX_instructions_unchanged=True,
        installer=installer, development=first, reboot=second, file_copy_and_persistence=True,
        original_master_unchanged=unchanged, original_master_sha256=original_hash,
        image=str(disk), directory=inspect(disk) if args.disk == '7902' else layout)
    (out / 'results.json').write_text(json.dumps(result, indent=2) + '\n')
    print(json.dumps({k: v for k, v in result.items() if k != 'directory'}, indent=2))
    return int(not unchanged)


if __name__ == '__main__':
    raise SystemExit(main())
