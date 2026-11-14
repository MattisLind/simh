"""Cross-link genuine XL RTLGN, then run it on the native RTE-L host.

This verifies generation only. XL BOOTEX/INSTL and target boot are separate
steps; successful generation is never reported as a booted operating system.
"""
import argparse
import hashlib
import json
import re
from pathlib import Path
from rte_archive import saver_tape
from rte_records import encode_text, decode_text
from run_rte_l_generation import host_files
from run_baseline import execute


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--simulator', type=Path, default=Path('BIN/hp2100'))
    parser.add_argument('--output', type=Path, default=Path('build/hp1000/rte-xl-generated'))
    parser.add_argument('--commands', type=Path, default=Path('tests/hp1000/config/rte-xl-7902.gen'))
    args = parser.parse_args()
    out = args.output
    out.mkdir(parents=True, exist_ok=True)
    kit = Path('hp1000-references/software/operating-systems/RTE-IVB')
    original = kit / 'RTE-IVB-SYSTEM.U0.7920H.disc'
    master = Path('hp1000-references/software/operating-systems/92071_RTE-XL_MasterDiscs_Rev2340/92071-13401_RTE-XL-1_REV2340.hpi')
    hashes = {str(p): hashlib.sha256(p.read_bytes()).hexdigest() for p in [original, master]}
    import shutil
    from rte_disk import inspect, append_files
    # Prerequisite: genuine disk-based L system and its matching cross-link host.
    l_build = Path('build/hp1000/rte-l-fmgr-generated')
    l_disk = Path('build/hp1000/rte-l-fmgr/rte-l-development-7902.hpi')
    development = Path('build/hp1000/rte-l-fmgr/development.ini')
    for required in [l_build / 'host.disc', l_disk, development]:
        if not required.exists():
            raise RuntimeError(f'Run run_rte_l_fmgr.py first: missing {required}')
    raw = master.read_bytes()
    entry = next(e for e in inspect(master)['files'] if e['name'] == '%RTLGN')
    generator = raw[entry['offset']:entry['offset'] + entry['bytes']]
    libraries = ['$SYSLB', '$FMP', '$DKLIB', '$CMDLB', '$MLIB1', '$MLIB2',
                 '$CLIBL', '$HPIB', '$MXLB', '$LDRLB']
    link = ('SN,SNAP::SC\n' + ''.join(f'LI,{lib}::SC\n' for lib in libraries)
            + 'OU,XLGN::SC\nRE,XGEN::SC\nEN\n')
    tape = out / 'input.tap'
    saver_tape(master, tape, [('XGEN', 5, generator),
               ('XGCMD', 3, encode_text(link))], file_names=[])
    host = out / 'host.disc'
    shutil.copyfile(l_build / 'host.disc', host)
    config = (kit / 'RTE-IVB.sim').read_text().rsplit('boot DA0', 1)[0]
    config = config.replace('set CPU IDLE', 'set CPU NOIDLE').replace(
        'attach DA0 RTE-IVB-SYSTEM.U0.7920H.disc', f'attach DA0 {host.resolve()}')
    c = ['set on', 'on error exit 1', config, f'attach -r MSC0 {tape.resolve()}',
         'runlimit 10000000', 'on error ignore', 'boot DA0', 'norunlimit',
         'send after=10000,delay=10000,"\\r"', 'step 1000000']
    def send(command, count=10000000):
        c.extend([f'send "{command}\\r"', f'step {count}'])
    for command in ['RU,FMGR', 'RU,READR', 'OC,SC', 'AL', 'EN', 'AB',
                    'RU,LOADR', 'SZ,24', 'LI,$LDRLB::SC', 'LI,$MXLB::SC']:
        send(command)
    send(r'RE,\045LOADR::SC', 200000000)
    send('EN', 30000000)
    send('RU,..ADR,XGCMD::SC', 500000000)
    c += ['echo HP1000_CHECK_PASS', 'exit']
    script = out / 'cross-link.ini'
    script.write_text('\n'.join(c) + '\n')
    cross = execute(args.simulator.resolve(), script, script.with_suffix('.log'), 600)
    if cross['status'] != 'PASS' or not re.search(r'\.\.ADR:XLGN\s+READY', script.with_suffix('.log').read_text()):
        raise RuntimeError('Original RTE-L loader did not cross-link XL RTLGN')
    kind, linked = host_files(host, ['XLGN'])['XLGN']
    (out / 'XLGN.bin').write_bytes(linked)
    disk = out / 'xl-generation-7902.hpi'
    text = args.commands.read_text().replace('::SC', '::32001')
    append_files(master, disk, [('XLGN', kind, linked), ('GENCMD', 3, encode_text(text))])
    data = bytearray(disk.read_bytes())
    # D.RTR cartridge-header word 3: separate reference from the L host.
    header = (inspect(disk)['tracks'] - 1) * 7680
    data[header + 6:header + 8] = (32001).to_bytes(2, 'big')
    disk.write_bytes(data)
    host_disk = out / 'rte-l-host.hpi'
    shutil.copyfile(l_disk, host_disk)
    console = out / 'console.txt'
    base = development.read_text().split('nobreak 2003', 1)[0]
    base = base.replace(str(l_disk.resolve()), str(host_disk.resolve()))
    old_console = Path('build/hp1000/rte-l-fmgr/development-console.txt').resolve()
    base = base.replace(str(old_console), str(console.resolve()))
    base = base.replace('deposit S 400', f'attach HPI1 {disk.resolve()}\ndeposit S 400')
    # =PLIB is Pascal relocatable support, unused by this generation. Purge
    # and pack only the working copy, using the authentic FMP operations.
    commands = ['MC,3', 'PU,=PLIB::32001', 'PK,32001',
        'RU,XLGN::32001,GENCMD::32001,SYLIST::32001,SYSTEM::32001,SNAP::32001']
    c = [base, 'nobreak 2003', r'expect -p "\005" send after=100,delay=100,"\006"; goto wait',
         'expect "FMGR : " goto command0', ':wait', 'on error ignore',
         'step 100000000', 'on error exit 1', 'exit AFAIL']
    for i, command in enumerate(commands):
        target = f'command{i + 1}' if i + 1 < len(commands) else 'done'
        c += [f':command{i}', f'expect "FMGR : " goto {target}',
              f'send after=10000,delay=10000,"{command}\\r"', 'goto wait']
    c += [':done', 'noexpect', 'echo HP1000_CHECK_PASS', 'exit']
    script = out / 'generate.ini'
    script.write_text('\n'.join(c) + '\n')
    run = execute(args.simulator.resolve(), script, script.with_suffix('.log'), 600)
    directory = inspect(disk)
    data = disk.read_bytes()
    files = {e['name']: (e['type'], data[e['offset']:e['offset'] + e['bytes']])
             for e in directory['files'] if e['name'] in ['SYSTEM', 'SNAP', 'SYLIST']}
    for name, (kind, payload) in files.items():
        (out / (name + '.bin')).write_bytes(payload)
    listing = decode_text(files['SYLIST'][1])
    (out / 'SYLIST.txt').write_text(listing)
    clean = bool(re.search(r'\*\s+0 ERRORS \*', listing)) and 'GEN AB' not in listing
    unchanged = all(hashlib.sha256(Path(p).read_bytes()).hexdigest() == checksum
                    for p, checksum in hashes.items())
    result = dict(status='PASS' if clean and unchanged and run['status'] == 'PASS' else 'FAIL',
                  generation_complete=clean, target_booted=False, software_patched=False,
                  original_sources_unchanged=unchanged, sources=hashes, execution=run,
                  files={name: dict(type=kind, bytes=len(payload),
                         sha256=hashlib.sha256(payload).hexdigest())
                         for name, (kind, payload) in files.items()})
    (out / 'results.json').write_text(json.dumps(result, indent=2) + '\n')
    print(json.dumps(result, indent=2))
    return int(result['status'] != 'PASS')


if __name__ == '__main__':
    raise SystemExit(main())
