"""Functional application checks on independent copies of the archive installation."""
import argparse
import json
import re
from pathlib import Path
from rte_7920 import make_image, read_volume
from rte_records import decode_text, encode_text
from run_baseline import execute

OUT = Path('build/hp1000/rte-xl-archive')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('package', choices=['edit', 'fortran', 'macro'])
    parser.add_argument('--system-disk',type=Path,
                        help='verified alternate system disk')
    args = parser.parse_args()
    package = args.package
    result = json.loads((OUT / (('fortran3' if package=='fortran' else package) + '-results.json')).read_text())
    if result['status'] != 'PASS':
        raise ValueError('package must link before functional testing')
    baseline = args.system_disk or Path('build/hp1000/rte-xl-languages/rte-xl-languages-7920.disc')
    volumes = {i: read_volume(baseline,i) for i in range(3)}
    volume = {'edit':3,'fortran':4,'macro':1}[package]
    volumes[volume] = read_volume(OUT / 'installation-7920.disc',volume)
    disk = OUT / (package + '-smoke.disc')
    if package=='fortran':
        volumes[4]['FSRC'] = (3,encode_text('FTN4\n      PROGRAM FTEST\n      INTEGER I\n      I=6*7\n      WRITE(1,100) I\n  100 FORMAT(1X,I5)\n      END\n'))
    if package=='fortran':
        link='SN,SNAP::32001\n'+''.join(f'LI,{n}::32001\n' for n in ['$MLIB1','$MLIB2','$FMP','$SYSLB','$MXLB'])+'OU,FTEST::32005\nRE,FOBJ::32005\nEN\n'
        volumes[4]['FLDCMD']=(3,encode_text(link))
    if package=='fortran':
        io="""FTN4
$FILES(0,1)
      PROGRAM FIOT
      INTEGER I,J
      I=42
      OPEN(UNIT=10,FILE='FDATA::32005',STATUS='NEW',
     1 MAXREC=8)
      WRITE(10,100) I
      CLOSE(10)
      OPEN(UNIT=10,FILE='FDATA::32005',STATUS='OLD',
     1 MAXREC=8)
      READ(10,100) J
      CLOSE(10)
      IF(J.NE.42) GO TO 900
      WRITE(1,200) J
      STOP
  900 WRITE(1,300)
  100 FORMAT(I5)
  200 FORMAT('FORTRAN FILE TEST PASSED ',I5)
  300 FORMAT('FORTRAN FILE TEST FAILED')
      END
"""
        rd="""FTN4
$FILES(0,1)
      PROGRAM FRDT
      INTEGER J
      OPEN(UNIT=10,FILE='FDATA::32005',STATUS='OLD',
     1 MAXREC=8)
      READ(10,100) J
      CLOSE(10)
      IF(J.NE.42) GO TO 900
      WRITE(1,200) J
      STOP
  900 WRITE(1,300)
  100 FORMAT(I5)
  200 FORMAT('FORTRAN REBOOT TEST PASSED ',I5)
  300 FORMAT('FORTRAN REBOOT TEST FAILED')
      END
"""
        common='SN,SNAP::32001\n'+''.join(f'LI,{n}::32001\n' for n in ['$MLIB1','$MLIB2','$FMP','$SYSLB','$MXLB'])
        for source_name,body,cmd,obj,exe in [('FIOSRC',io,'FIOLD','FIOOBJ','FIOTST'),('FRSRC',rd,'FRLD','FROBJ','FRTEST')]:
            volumes[4][source_name]=(3,encode_text(body))
            volumes[4][cmd]=(3,encode_text(common+f'OU,{exe}::32005\nRE,{obj}::32005\nEN\n'))
    if package=='macro':
        from run_rte_l_fmgr import HELLO
        plain=HELLO.replace('ASMB,R,L','MACRO,R,L')
        macro=plain.replace('      EXT REIO,EXEC',
            '      MACRO\n      ADDONE\n      ADA =D1\n      ENDMAC\n      EXT REIO,EXEC').replace('      ADA =D1\n      CPA', '      ADDONE\n      CPA')
        volumes[1]['&PLAIN']=(3,encode_text(plain))
        volumes[1]['&MAC']=(3,encode_text(macro))
        common='SN,SNAP::32001\n'+''.join(f'LI,{n}::32001\n' for n in ['$SYSLB','$FMP','$MLIB1','$MLIB2','$MXLB'])
        for cmd,obj,exe in [('PLLINK','PLREL','MCPLN'),('MCLINK','MCREL','MCMAC')]:
            volumes[1][cmd]=(3,encode_text(common+f'OU,{exe}::32002\nRE,{obj}::32002\nEN\n'))
    make_image(disk,volumes)
    base = Path('build/hp1000/rte-xl-7920')
    console = OUT / (package + '-smoke-console.txt')
    console.write_bytes(b'')
    prefix=(base/'development.ini').read_text().split(':prompt0\n',1)[0].replace(
        str((base/'rte-xl-7920.disc').resolve()),str(disk.resolve())).replace(
        str((base/'development-console.txt').resolve()),str(console.resolve())).replace('step 200000000','step 500000000')
    if package=='edit':
        # Minimal HP264x terminal test fixture: primary status response,
        # 4KB memory, line mode, block mode/auto-LF disabled. Format is
        # 02645-90005 Nov.1978 section 6: ESC backslash, seven status
        # bytes, CR. EDIT/XL's TYPEQ treats both DT0 and DT5 as screen
        # terminals, so merely selecting M2621 does not avoid this query.
        prefix=prefix.replace('expect "FMGR :',
            r'expect -p "\033^\021" send after=100000,delay=100000,"\033\1344001468\r"; goto wait'+'\nexpect "FMGR :',1)
        steps=[('FMGR : \\021','MC,5'),('FMGR : \\021','RU,EDIT::32004'),
            ('\\r/\\021','IHELLO EDIT'),('\\r/\\021','EC,EDSRC::32004'),
            ('FMGR : \\021','RU,EDIT::32004,EDSRC::32004'),('\\r/\\021','1 $ L'),
            ('\\r/\\021','H I'),('\\r/\\021','A/')]
    elif package=='fortran':
        steps=[('FMGR : \\021','MC,6'),('FMGR : \\021','RU,FTN4X::32005,FSRC::32005,FLIST::32005,FOBJ::32005'),('FMGR : \\021','RU,LOADR,FLDCMD::32005'),('FMGR : \\021','RU,FTEST::32005')]
    else:
        steps=[('FMGR : \\021','MC,3')]+[('FMGR : \\021',c) for c in [
            'RU,MACRO::32002,&PLAIN::32002,PLLIST::32002,PLREL::32002',
            'RU,LOADR,PLLINK::32002','RU,MCPLN::32002',
            'RU,MACRO::32002,&MAC::32002,MCLIST::32002,MCREL::32002',
            'RU,LOADR,MCLINK::32002','RU,MCMAC::32002']]
    if package=='fortran':
        steps += [('FMGR : \\021',c) for c in [
            'RU,FTN4X::32005,FIOSRC::32005,FIOLST::32005,FIOOBJ::32005',
            'RU,LOADR,FIOLD::32005','RU,FIOTST::32005',
            'RU,FTN4X::32005,FRSRC::32005,FRLIST::32005,FROBJ::32005',
            'RU,LOADR,FRLD::32005']]
    # The final command's completion is the final FMGR prompt. Install that
    # expectation before sending it, rather than waiting on the old pattern.
    c = [prefix]
    for i,(pattern,command) in enumerate(steps):
        next_pattern = steps[i+1][0] if i+1<len(steps) else 'FMGR : \\021'
        ending = '' if command == r'\r\n' else r'\r'
        c += [f':prompt{i}', f'expect "{next_pattern}" goto prompt{i+1}',
              f'send after=100000,delay=100000,"{command}{ending}"','goto wait']
    c += [f':prompt{len(steps)}','noexpect','echo HP1000_CHECK_PASS','exit']
    # Prefix already waits for the first FMGR prompt and branches prompt0.
    script=OUT/(package+'-smoke.ini');script.write_text('\n'.join(c)+'\n')
    run=execute(Path('BIN/hp2100').resolve(),script,script.with_suffix('.log'),900)
    text=console.read_text(errors='replace')
    files=read_volume(disk,volume)
    if package=='edit':
        saved=decode_text(files['EDSRC'][1]) if 'EDSRC' in files else None
        passed=run['status']=='PASS' and saved=='HELLO EDIT\n' and 'Insert text before current line' in text
        detail=dict(saved=saved,help_displayed='Insert text before current line' in text)
    elif package=='fortran':
        passed=run['status']=='PASS' and 'FOBJ' in files and files['FOBJ'][0]==5 and 'NO DISASTERS,  NO ERRORS' in text and bool(re.search(r'(?:^|[\r\n])[ \t]*42[ \t]*(?:[\r\n]|$)',text.replace('\x05',''))) and 'ABORTED' not in text
        from run_rte_xl_archive import session
        saved=files.get('FDATA')
        reboot,output=session('fortran-file-reboot',['MC,6','RU,FRTEST::32005'],disk=disk)
        unchanged=read_volume(disk,4).get('FDATA')==saved
        io_pass='FORTRAN FILE TEST PASSED' in text and 'FORTRAN REBOOT TEST PASSED' in output and unchanged and saved is not None
        passed=passed and io_pass and reboot['status']=='PASS'
        detail=dict(object_created='FOBJ' in files,MAXREC_file_IO=io_pass,fresh_boot=reboot,data_file_persistent=unchanged and saved is not None)
    else:
        passed=run['status']=='PASS' and text.count('ASSEMBLY TEST PASSED')==2 and 'ASSEMBLY TEST FAILED' not in text and all(n in files for n in ['PLREL','MCREL','MCPLN','MCMAC'])
        detail=dict(plain_and_macro_programs_passed=passed)
    report=dict(status='PASS' if passed else 'FAIL',package=package,macro_revision='2340' if package=='macro' else None,functional_smoke_pass=passed,run=run,**detail)
    (OUT/(package+'-smoke-results.json')).write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps(report,indent=2))
    return int(not passed)


if __name__=='__main__':
    raise SystemExit(main())
