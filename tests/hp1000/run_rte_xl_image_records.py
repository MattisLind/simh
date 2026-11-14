"""Compile and run IMAGE/L API tests, then verify a record after a fresh boot."""
import json
import re
from pathlib import Path
from rte_7920 import read_volume,make_image
from rte_records import encode_text,decode_text
from run_rte_xl_archive import OUT,session

HEADER="""FTN4
      PROGRAM DBTST
      INTEGER BASE(7),LEVEL(3),STAT(10),LIST(1),BUF,ARG(2),STEP
      DATA BASE/2H  ,2HTD,2HB:,2H1:,2H32,2H01,2H0 /
      DATA LEVEL/2HTE,2HST,2H  /,LIST/2H@ /,ARG/0,0/
      STEP=1
      CALL DBOPN(BASE,LEVEL,3,STAT)
      IF(STAT(1).NE.0) GO TO 900
"""
WRITER="""      BUF=42
      STEP=2
      CALL DBPUT(BASE,1,1,STAT,LIST,BUF)
      IF(STAT(1).NE.0) GO TO 900
      BUF=0
      STEP=3
      CALL DBGET(BASE,1,1,STAT,LIST,BUF,ARG)
      IF(STAT(1).NE.0.OR.BUF.NE.42) GO TO 900
      BUF=43
      STEP=4
      CALL DBUPD(BASE,1,1,STAT,LIST,BUF)
      IF(STAT(1).NE.0) GO TO 900
      BUF=0
      STEP=5
      CALL DBGET(BASE,1,1,STAT,LIST,BUF,ARG)
      IF(STAT(1).NE.0.OR.BUF.NE.43) GO TO 900
"""
READER="""      BUF=0
      STEP=3
      CALL DBGET(BASE,1,2,STAT,LIST,BUF,ARG)
      IF(STAT(1).NE.0.OR.BUF.NE.43) GO TO 900
"""
TRAILER="""      STEP=6
      CALL DBCLS(BASE,1,1,STAT)
      IF(STAT(1).NE.0) GO TO 900
      WRITE(1,100) BUF
      STOP
  900 WRITE(1,200) STEP,STAT(1),BUF
      STOP
  100 FORMAT('IMAGE RECORD TEST PASSED ',I5)
  200 FORMAT('IMAGE RECORD TEST FAILED STEP/STATUS/VALUE ',3I6)
      END
"""


def main():
    if json.loads((OUT/'image-schema-results.json').read_text())['status']!='PASS':
        raise ValueError('successful database creation required')
    volumes={v:read_volume(OUT/'image-schema.disc',v) for v in range(10)}
    volumes[4]=read_volume(OUT/'fortran-smoke.disc',4)
    # DBOPN schedules the authentic DBCOP coordinator (error 140 means it
    # cannot schedule it). Register it through original BOOTEX's ordinary
    # resident-program directive before starting FMGR, not a simulator hook.
    volumes[0]['DBCOP']=volumes[9]['DBCOP']
    boot=decode_text(volumes[0]['BOOT'][1])
    volumes[0]['BOOT']=(3,encode_text(boot.replace('RP,FMGR\n','RP,DBCOP\nSZ,4\nRP,FMGR\n')))
    common='SN,SNAP::32001\n'+''.join(f'LI,{n}::32010\n' for n in ['$DBMS1','%DECAR'])+''.join(f'LI,{n}::32001\n' for n in ['$MLIB1','$MLIB2','$FMP','$SYSLB','$MXLB'])
    for source,obj,cmd,name,body in [('DBSRC','DBOBJ','DBLINK','DBTST',WRITER),('DBRSRC','DBROBJ','DBRLNK','DBRDT',READER)]:
        volumes[9][source]=(3,encode_text(HEADER.replace('PROGRAM DBTST',f'PROGRAM {name}')+body+TRAILER))
        volumes[9][cmd]=(3,encode_text(common+f'OU,{name}::32010\nSZ,32\nRE,{obj}::32010\nEN\n'))
    disk=OUT/'image-records.disc';make_image(disk,volumes)
    commands=['MC,6','MC,11']
    for source,obj,lst,cmd in [('DBSRC','DBOBJ','DBLIST','DBLINK'),('DBRSRC','DBROBJ','DBRLST','DBRLNK')]:
        commands += [f'RU,FTN4X::32005,{source}::32010,{lst}::32010,{obj}::32010',f'RU,LOADR,{cmd}::32010']
    commands += ['RU,DBTST::32010']
    run,text=session('image-records',commands,disk=disk)
    reboot,output=session('image-records-reboot',['MC,11','RU,DBRDT::32010'],disk=disk)
    passed=all(r['status']=='PASS' for r in [run,reboot]) and 'IMAGE RECORD TEST PASSED' in text and 'IMAGE RECORD TEST PASSED' in output and 'IMAGE RECORD TEST FAILED' not in text+output and 'ABORTED' not in text+output
    report=dict(status='PASS' if passed else 'FAIL',execution=run,reboot=reboot,
                persistent_database_accepted=passed,
                failures=[dict(step=int(a),status=int(b),value=int(c))
                          for a,b,c in re.findall(r'FAILED STEP/STATUS/VALUE\s+(\d+)\s+(-?\d+)\s+(-?\d+)',text+output)])
    (OUT/'image-records-results.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps(report,indent=2));return int(not passed)


if __name__=='__main__':raise SystemExit(main())
