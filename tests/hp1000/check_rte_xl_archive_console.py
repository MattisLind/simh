"""Check the public console launcher and HP status fixture with genuine EDIT."""
import errno
import json
import os
import pty
import select
import shutil
import time
from pathlib import Path
from run_rte_xl_archive import OUT


def main():
    image=OUT/'console-check.disc'
    shutil.copyfile(OUT/'rte-xl-software-7920.disc',image)
    script=Path('tests/hp1000/run_rte_xl.py').resolve()
    pid,master=pty.fork()
    if pid==0:
        os.execvp('python3',['python3',str(script),'--image',str(image.resolve()),'--hp264x-status'])
    steps=[(b'FMGR : \x11',b'MC,5\r'),(b'FMGR : \x11',b'RU,EDIT::32004,EDSRC::32004\r'),
           (b'\r/\x11',b'1 $ L\r'),(b'\r/\x11',b'H I\r'),
           (b'\r/\x11',b'A/\r'),(b'FMGR : \x11',b'\x05'),(b'sim> ',b'quit\r')]
    data=bytearray();buffer=bytearray();pending=bytearray();state=0
    started=time.monotonic();next_key=started;timed_out=False
    try:
        while True:
            if time.monotonic()-started>180:
                timed_out=True;os.kill(pid,15);break
            ready,_,_=select.select([master],[],[],.005)
            if ready:
                try:chunk=os.read(master,65536)
                except OSError as exc:
                    if exc.errno==errno.EIO:break
                    raise
                if not chunk:break
                data.extend(chunk);buffer.extend(chunk)
            if state<len(steps) and not pending:
                pattern,command=steps[state];at=buffer.find(pattern)
                if at>=0:
                    del buffer[:at+len(pattern)];pending.extend(command);state+=1
                    next_key=time.monotonic()+.1
            if pending and time.monotonic()>=next_key:
                os.write(master,pending[:1]);del pending[:1];next_key=time.monotonic()+.01
    finally:
        os.close(master);_,status=os.waitpid(pid,0)
    (OUT/'public-console-check.txt').write_bytes(data)
    passed=not timed_out and os.waitstatus_to_exitcode(status)==0 and state==len(steps) and b'HELLO EDIT' in data and b'Insert text before current line' in data
    result=dict(status='PASS' if passed else 'FAIL',timed_out=timed_out,steps=state)
    (OUT/'public-console-check-results.json').write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps(result,indent=2));return int(not passed)


if __name__=='__main__':raise SystemExit(main())
