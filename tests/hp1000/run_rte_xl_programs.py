"""Cross-link XL LOADR on IVB, then link authentic XL programs under native L.

Requires the verified RTE-L/FMGR host and run_rte_xl_generation.py outputs.
All executables and libraries come unchanged from HP distribution media.
"""
import argparse
import hashlib
import json
import re
import shutil
from pathlib import Path
from rte_archive import saver_tape
from rte_disk import inspect, pack_files
from rte_records import encode_text
from run_rte_l_generation import host_files
from run_baseline import execute


def payloads(image):
    data = image.read_bytes()
    return {e['name']: (e['type'], data[e['offset']:e['offset'] + e['bytes']])
            for e in inspect(image)['files']}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--simulator', type=Path, default=Path('BIN/hp2100'))
    parser.add_argument('--output', type=Path, default=Path('build/hp1000/rte-xl-programs'))
    parser.add_argument('--generated', type=Path, default=Path('build/hp1000/rte-xl-generated'))
    args = parser.parse_args()
    out = args.output
    out.mkdir(parents=True, exist_ok=True)
    root = Path('hp1000-references/software/operating-systems/92071_RTE-XL_MasterDiscs_Rev2340')
    master = root / '92071-13401_RTE-XL-1_REV2340.hpi'
    second = root / '92071-13415_RTE-XL-2_REV2340.hpi'
    sources = {str(p): hashlib.sha256(p.read_bytes()).hexdigest() for p in [master, second]}
    m1, m2 = payloads(master), payloads(second)
    libraries = ['XLDLIB', '$SYSLB', '$FMP', '$DKLIB', '$CMDLB', '$MLIB1',
                 '$MLIB2', '$CLIBL', '$HPIB', '$MXLB']
    link = ('SN,SNAP::SC\n' + ''.join(f'LI,{lib}::SC\n' for lib in libraries)
            + 'OU,XLOAD::SC\nRE,XRELO::SC\nEN\n')
    tape = out / 'loader.tap'
    saver_tape(master, tape, [('XRELO', *m2['%LOADR']),
        ('XLDLIB', *m1['$LDRLN']), ('XLCMD', 3, encode_text(link))], file_names=[])
    kit = Path('hp1000-references/software/operating-systems/RTE-IVB')
    host = out / 'host.disc'
    shutil.copyfile('build/hp1000/rte-l-fmgr-generated/host.disc', host)
    config = (kit / 'RTE-IVB.sim').read_text().rsplit('boot DA0', 1)[0]
    config = config.replace('set CPU IDLE', 'set CPU NOIDLE').replace(
        'attach DA0 RTE-IVB-SYSTEM.U0.7920H.disc', f'attach DA0 {host.resolve()}')
    c = ['set on', 'on error exit 1', config, f'attach -r MSC0 {tape.resolve()}',
         'runlimit 10000000', 'on error ignore', 'boot DA0', 'norunlimit',
         r'send after=10000,delay=10000,"\r"', 'step 1000000']
    def send(command, instructions=10000000):
        c.extend([f'send "{command}\\r"', f'step {instructions}'])
    for command in ['RU,FMGR', 'RU,READR', 'OC,SC', 'AL', 'EN', 'AB',
                    'RU,LOADR', 'SZ,24', 'LI,$LDRLB::SC', 'LI,$MXLB::SC']:
        send(command)
    send(r'RE,\045LOADR::SC', 200000000)
    send('EN', 30000000)
    send('RU,..ADR,XLCMD::SC', 500000000)
    c += ['echo HP1000_CHECK_PASS', 'exit']
    script = out / 'cross-link.ini'
    script.write_text('\n'.join(c) + '\n')
    cross = execute(args.simulator.resolve(), script, script.with_suffix('.log'), 600)
    transcript = script.with_suffix('.log').read_text()
    if cross['status'] != 'PASS' or not re.search(r'\.\.ADR:XLOAD\s+READY', transcript):
        raise RuntimeError('cross-linking XL LOADR failed')
    loader = host_files(host, ['XLOAD'])['XLOAD']
    (out / 'XLOAD.bin').write_bytes(loader[1])
    files = {n: f for n, f in m1.items() if n not in ['=PLIB', '%PFORM', '%BUILD', '%RTLGN']}
    files['XLOAD'] = loader
    files['SNAP'] = (3, (args.generated / 'SNAP.bin').read_bytes())
    libraries = ['$SYSLB', '$FMP', '$DKLIB', '$CMDLB', '$MLIB1', '$MLIB2', '$MXLB', '$LDRLN']
    # Explicit SG count matches the original FMGR's LOD 2,SG,7 directive.
    command = ('SN,SNAP::32001\n' + ''.join(f'LI,{lib}::32001\n' for lib in libraries)
               + 'OU,FMGR::32001\nSG,7\nRE,%FMGR::32001\nEN\n')
    files['FMCMD'] = (3, encode_text(command))
    files['DRCMD'] = (3, encode_text(command.replace('OU,FMGR::32001\nSG,7\nRE,%FMGR', 'OU,D.RTR::32001\nRE,%D.RTR'))) 
    disk = out / 'native-link-work.hpi'
    pack_files(master, disk, files, 32001)
    l_disk = Path('build/hp1000/rte-l-fmgr/rte-l-development-7902.hpi')
    native_host = out / 'native-host.hpi'
    shutil.copyfile(l_disk, native_host)
    console = out / 'console.txt'
    console.write_bytes(b'')
    base = Path('build/hp1000/rte-l-fmgr/development.ini').read_text().split('nobreak 2003', 1)[0]
    base = base.replace(str(l_disk.resolve()), str(native_host.resolve())).replace(
        str(Path('build/hp1000/rte-l-fmgr/development-console.txt').resolve()), str(console.resolve()))
    base = base.replace('deposit S 400', f'attach HPI1 {disk.resolve()}\ndeposit S 400')
    c = [base, 'nobreak 2003', r'expect -p "\005" send after=100,delay=100,"\006"; goto wait',
         'expect "FMGR : " goto mount', ':wait', 'on error ignore', 'step 500000000',
         'on error exit 1', 'exit AFAIL', ':mount', 'expect "FMGR : " goto link',
         r'send after=10000,delay=10000,"MC,3\r"', 'goto wait', ':link',
         'expect "FMGR : " goto directory',
         r'send after=10000,delay=10000,"RU,XLOAD::32001,FMCMD::32001\r"',
         'goto wait', ':directory', 'expect "FMGR : " goto done',
         r'send after=10000,delay=10000,"RU,XLOAD::32001,DRCMD::32001\r"',
         'goto wait', ':done', 'noexpect', 'echo HP1000_CHECK_PASS', 'exit']
    script = out / 'native-link.ini'
    script.write_text('\n'.join(c) + '\n')
    run = execute(args.simulator.resolve(), script, script.with_suffix('.log'), 900)
    text = console.read_text(errors='replace')
    clean = bool(re.search(r'XLOAD:FMGR\s+READY', text)) and not re.search(r'ABORTED|IL MRG|UN EXT|NM SEG', text)
    if not clean or run['status'] != 'PASS':
        raise RuntimeError('native XL FMGR cross-link failed; see console.txt')
    programs = {}
    for name in ['FMGR', 'D.RTR']:
        kind, native = payloads(disk)[name]
        (out / (name + '.bin')).write_bytes(native)
        programs[name] = dict(type=kind, bytes=len(native), sha256=hashlib.sha256(native).hexdigest())
    if not re.search(r'XLOAD:D\.RTR\s+READY', text):
        raise RuntimeError('D.RTR did not link')
    unchanged = all(hashlib.sha256(Path(p).read_bytes()).hexdigest() == h for p, h in sources.items())
    result = dict(status='PASS' if unchanged else 'FAIL', original_sources_unchanged=unchanged,
        sources=sources, cross_link=cross, native_link=run, software_patched=False,
        programs=programs)
    (out / 'results.json').write_text(json.dumps(result, indent=2) + '\n')
    print(json.dumps(result, indent=2))
    return int(result['status'] != 'PASS')


if __name__ == '__main__':
    raise SystemExit(main())
