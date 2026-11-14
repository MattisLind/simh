"""Run HP XL RTLGN with #PANS on the verified native L cross-generation host.

Native XL execution of RTLGN aborted MP; the supported, previously validated L
host is used instead. A compact input cartridge preserves every selected record
and leaves room for SYSTEM/SNAP/listing, without requiring another I/O interface.
"""
import json
import argparse
import re
import shutil
from pathlib import Path
from rte_7920 import read_volume
from rte_disk import pack_files,inspect
from rte_records import decode_text,encode_text
from run_baseline import execute
from rte_xl_boot import snapshot_symbols


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--line-console-only', action='store_true',
                        help='generate baseline XL with M2621, without Pascal inserts')
    args=parser.parse_args()
    source=Path('build/hp1000/rte-xl-archive/installation-7920.disc')
    out=Path('build/hp1000/rte-xl-line-generated' if args.line_console_only else 'build/hp1000/rte-xl-pascal-generated');out.mkdir(parents=True,exist_ok=True)
    volumes={v:read_volume(source,v) for v in [0,5,6]}
    text=decode_text(volumes[6]['PASGEN'][1]).replace('::32006','::32001')
    # Rev.2340 already defines both entries as RPL 2001B; the Rev.2144
    # compatibility module repeats these identical definitions (DU ENT).
    # Keep HP's original #PANS intact and omit only this redundant REL in
    # our separately named, configuration-specific generation commands.
    symbols=snapshot_symbols(volumes[0]['SNAP'][1])
    if any(symbols.get(name)!=0o2001 for name in ['.ZPRV','.ZRNT']):
        raise ValueError('cannot omit %ZPRV: system bindings differ from its RPLs')
    text=text.replace('REL,%ZPRV::32001', '* Rev.2340 already defines .ZPRV and .ZRNT as 2001B')
    if args.line_console_only:
        text=Path('tests/hp1000/config/rte-xl-7920.gen').read_text().replace('::SC','::32001').replace('M2645','M2621')
    files={}
    for line in text.splitlines():
        if line.startswith(('RE,','REL,','SE,','MS,','LI,$')) and '::' in line:
            name=line.split(',')[1].split('::')[0].strip()
            files[name]=(volumes[5] if name in volumes[5] else volumes[0])[name]
    files['XLGN']=(6,Path('build/hp1000/rte-xl-7920-generated/XLGN.bin').read_bytes())
    files['GENCMD']=(3,encode_text(text))
    (out/'commands.gen').write_text(text)
    master=Path('hp1000-references/software/operating-systems/92071_RTE-XL_MasterDiscs_Rev2340/92071-13401_RTE-XL-1_REV2340.hpi')
    disk=out/'generation.hpi';pack_files(master,disk,files,32001)
    l_disk=Path('build/hp1000/rte-l-fmgr/rte-l-development-7902.hpi');host=out/'host.hpi';shutil.copyfile(l_disk,host)
    console=out/'console.txt';console.write_bytes(b'')
    base=Path('build/hp1000/rte-l-fmgr/development.ini').read_text().split('nobreak 2003',1)[0]
    base=base.replace(str(l_disk.resolve()),str(host.resolve())).replace(str(Path('build/hp1000/rte-l-fmgr/development-console.txt').resolve()),str(console.resolve()))
    base=base.replace('deposit S 400',f'attach HPI1 {disk.resolve()}\ndeposit S 400')
    c=[base,'nobreak 2003',r'expect -p "\005" send after=10000,delay=10000,"\006"; goto wait','expect "FMGR : \\021" goto mount',':wait','on error ignore','step 1000000000','on error exit 1','exit AFAIL',':mount','expect "FMGR : \\021" goto generate',r'send after=10000,delay=10000,"MC,3\r"','goto wait',':generate','expect "FMGR : \\021" goto done',r'send after=10000,delay=10000,"RU,XLGN::32001,GENCMD::32001,SYLIST::32001,SYSTEM::32001,SNAP::32001\r"','goto wait',':done','noexpect','echo HP1000_CHECK_PASS','exit']
    script=out/'generate.ini';script.write_text('\n'.join(c)+'\n')
    run=execute(Path('BIN/hp2100').resolve(),script,script.with_suffix('.log'),1200)
    data=disk.read_bytes();actual=inspect(disk)
    listing=''
    for entry in actual['files']:
        if entry['name'] in ['SYSTEM','SNAP','SYLIST']:
            binary=data[entry['offset']:entry['offset']+entry['bytes']]
            (out/(entry['name']+'.bin')).write_bytes(binary)
            if entry['name']=='SYLIST':listing=decode_text(binary);(out/'SYLIST.txt').write_text(listing)
    passed=run['status']=='PASS' and bool(re.search(r'\*\s+0 ERRORS \*',listing)) and 'GEN AB' not in listing
    result=dict(status='PASS' if passed else 'FAIL',execution=run,source='baseline XL configuration' if args.line_console_only else '#PANS 92854-17003 Rev.2144',console_model='M2621',software_patched=False)
    (out/'results.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result,indent=2))
    return int(not passed)


if __name__=='__main__':raise SystemExit(main())
