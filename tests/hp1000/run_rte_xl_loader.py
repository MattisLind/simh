"""Link a native XL LOADR against the generated snapshot on the verified L host."""
import argparse
import hashlib
import json
import re
import shutil
from pathlib import Path
from run_rte_xl_programs import payloads
from rte_disk import pack_files
from rte_records import encode_text
from run_baseline import execute


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, default=Path('build/hp1000/rte-xl-loader'))
    args = parser.parse_args()
    out = args.output
    out.mkdir(parents=True, exist_ok=True)
    root = Path('hp1000-references/software/operating-systems/92071_RTE-XL_MasterDiscs_Rev2340')
    master = root / '92071-13401_RTE-XL-1_REV2340.hpi'
    second = root / '92071-13415_RTE-XL-2_REV2340.hpi'
    original = {str(p): hashlib.sha256(p.read_bytes()).hexdigest() for p in [master, second]}
    m1, m2 = payloads(master), payloads(second)
    libraries = ['$LDRLN', '$SYSLB', '$FMP', '$DKLIB', '$CMDLB', '$MLIB1', '$MLIB2', '$MXLB']
    files = {name: m1[name] for name in libraries}
    files['XLOAD'] = (6, Path('build/hp1000/rte-xl-programs/XLOAD.bin').read_bytes())
    files['SNAP'] = (3, Path('build/hp1000/rte-xl-7920-generated/SNAP.bin').read_bytes())
    files['%LOADR'] = m2['%LOADR']
    command = ('SN,SNAP::32001\n' + ''.join(f'LI,{n}::32001\n' for n in libraries)
               + 'OU,LOADR::32001\nSG,3\nSZ,32\nRE,%LOADR::32001\nEN\n')
    files['LDCMD'] = (3, encode_text(command))
    disk = out / 'link.hpi'
    pack_files(master, disk, files, 32001)
    source_host = Path('build/hp1000/rte-l-fmgr/rte-l-development-7902.hpi')
    host = out / 'host.hpi'
    shutil.copyfile(source_host, host)
    console = out / 'console.txt'
    console.write_bytes(b'')
    base = Path('build/hp1000/rte-l-fmgr/development.ini').read_text().split('nobreak 2003', 1)[0]
    base = base.replace(str(source_host.resolve()), str(host.resolve())).replace(
        str(Path('build/hp1000/rte-l-fmgr/development-console.txt').resolve()), str(console.resolve()))
    base = base.replace('deposit S 400', f'attach HPI1 {disk.resolve()}\ndeposit S 400')
    c = [base, 'nobreak 2003', r'expect -p "\005" send after=10000,delay=10000,"\006"; goto wait',
         'expect "FMGR : \\021" goto mount', ':wait', 'on error ignore', 'step 500000000',
         'on error exit 1', 'exit AFAIL', ':mount', 'expect "FMGR : \\021" goto link',
         r'send after=10000,delay=10000,"MC,3\r"', 'goto wait', ':link',
         'expect "FMGR : \\021" goto done',
         r'send after=10000,delay=10000,"RU,XLOAD::32001,LDCMD::32001\r"',
         'goto wait', ':done', 'noexpect', 'echo HP1000_CHECK_PASS', 'exit']
    script = out / 'link.ini'
    script.write_text('\n'.join(c) + '\n')
    run = execute(Path('BIN/hp2100').resolve(), script, script.with_suffix('.log'), 900)
    text = console.read_text(errors='replace')
    if run['status'] != 'PASS' or not re.search(r'XLOAD:LOADR\s+READY', text) or re.search(r'ABORTED|IL MRG|UN EXT|NM SEG', text):
        raise RuntimeError('native XL loader link failed: ' + str(console))
    kind, binary = payloads(disk)['LOADR']
    (out / 'LOADR.bin').write_bytes(binary)
    unchanged = all(hashlib.sha256(Path(p).read_bytes()).hexdigest() == h for p, h in original.items())
    result = dict(status='PASS' if unchanged else 'FAIL', type=kind, bytes=len(binary),
                  sha256=hashlib.sha256(binary).hexdigest(), original_sources_unchanged=unchanged, sources=original, run=run)
    (out / 'results.json').write_text(json.dumps(result, indent=2) + '\n')
    print(json.dumps(result, indent=2))
    return int(not unchanged)


if __name__ == '__main__':
    raise SystemExit(main())
