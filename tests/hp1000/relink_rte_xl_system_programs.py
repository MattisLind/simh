"""Relink XL FMGR, D.RTR and LOADR against the generated Pascal snapshot.

Uses the previously verified L-host XLOAD cross-loader and unchanged HP master
relocatables. Existing program files were linked to a different SYSTEM; reusing
those files after moving system entries is not a valid installation.
"""
import json
import re
import shutil
from pathlib import Path
from rte_7920 import read_volume, make_image
from rte_disk import pack_files
from rte_records import encode_text
from run_rte_xl_boot import payloads
from run_baseline import execute
from run_rte_xl_archive import OUT, session


def main():
    out=Path('build/hp1000/rte-xl-pascal-relinked');out.mkdir(parents=True,exist_ok=True)
    root=Path('hp1000-references/software/operating-systems/92071_RTE-XL_MasterDiscs_Rev2340')
    master=root/'92071-13401_RTE-XL-1_REV2340.hpi'
    files=payloads(master)
    for name in ['=PLIB','%PFORM','%BUILD','%RTLGN']:files.pop(name,None)
    files['SNAP']=(3,Path('build/hp1000/rte-xl-pascal-generated/SNAP.bin').read_bytes())
    files['XLOAD']=(6,Path('build/hp1000/rte-xl-programs/XLOAD.bin').read_bytes())
    files['%LOADR']=payloads(root/'92071-13415_RTE-XL-2_REV2340.hpi')['%LOADR']
    libraries=['$SYSLB','$FMP','$DKLIB','$CMDLB','$MLIB1','$MLIB2','$MXLB','$LDRLN']
    common='SN,SNAP::32001\n'+''.join(f'LI,{n}::32001\n' for n in libraries)
    for cmd,name,sg in [('FMCMD','FMGR',7),('DRCMD','D.RTR',0),('LDCMD','LOADR',4)]:
        files[cmd]=(3,encode_text(common+f'OU,{name}::32001\nSZ,32\nSG,{sg}\nRE,%{name}::32001\nEN\n'))
    disk=out/'link.hpi';pack_files(master,disk,files,32001)
    original=Path('build/hp1000/rte-l-fmgr/rte-l-development-7902.hpi')
    host=out/'host.hpi';shutil.copyfile(original,host)
    console=out/'console.txt';console.write_bytes(b'')
    prefix=Path('build/hp1000/rte-l-fmgr/development.ini').read_text().split('nobreak 2003',1)[0]
    prefix=prefix.replace(str(original.resolve()),str(host.resolve())).replace(str(Path('build/hp1000/rte-l-fmgr/development-console.txt').resolve()),str(console.resolve()))
    prefix=prefix.replace('deposit S 400',f'attach HPI1 {disk.resolve()}\ndeposit S 400')
    commands=['MC,3']+[f'RU,XLOAD::32001,{c}::32001' for c in ['FMCMD','DRCMD','LDCMD']]
    c=[prefix,'nobreak 2003',r'expect -p "\005" send after=10000,delay=10000,"\006"; goto wait','expect "FMGR : \\021" goto prompt0',':wait','on error ignore','step 2000000000','on error exit 1','exit AFAIL']
    for i,command in enumerate(commands):
        c += [f':prompt{i}',f'expect "FMGR : \\021" goto prompt{i+1}',f'send after=10000,delay=10000,"{command}\\r"','goto wait']
    c += [f':prompt{len(commands)}','noexpect','echo HP1000_CHECK_PASS','exit']
    script=out/'link.ini';script.write_text('\n'.join(c)+'\n')
    run=execute(Path('BIN/hp2100').resolve(),script,script.with_suffix('.log'),1200)
    text=console.read_text(errors='replace')
    passed=run['status']=='PASS' and all(re.search(r'XLOAD:'+re.escape(n)+r'\s+READY',text) for n in ['FMGR','D.RTR','LOADR']) and not re.search('UN EXT|IL MRG|ABORTED|NM SEG',text)
    result=dict(status='PASS' if passed else 'FAIL',execution=run)
    if passed:
        image=OUT/'pascal-system-7920.disc'
        volumes={v:read_volume(image,v) for v in range(10)}
        for name in ['FMGR','D.RTR','LOADR']:volumes[0][name]=payloads(disk)[name]
        make_image(image,volumes)
        boot,output=session('pascal-relinked-boot',['DL'],disk=image)
        result['boot']=boot
        result['status']=boot['status']
    (out/'results.json').write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps(result,indent=2));return int(result['status']!='PASS')


if __name__=='__main__':raise SystemExit(main())
