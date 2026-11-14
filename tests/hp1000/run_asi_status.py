"""Run authentic EDIT with ASI LOCALACK/LOCALSTATUS and no host responders."""
import json
import shutil
from pathlib import Path
from rte_7920 import read_volume
from rte_records import decode_text
from run_baseline import execute


def main():
    out=Path('build/hp1000/asi-localstatus');out.mkdir(parents=True,exist_ok=True)
    disk=out/'working.disc'
    shutil.copyfile('build/hp1000/rte-xl-archive/rte-xl-software-7920.disc',disk)
    base=Path('build/hp1000/rte-xl-archive/edit-smoke.ini').read_text()
    base=base.replace(str(Path('build/hp1000/rte-xl-archive/edit-smoke.disc').resolve()),str(disk.resolve()))
    console=out/'console.txt';console.write_bytes(b'')
    base=base.replace(str(Path('build/hp1000/rte-xl-archive/edit-smoke-console.txt').resolve()),str(console.resolve()))
    base=base.replace('set ASI enabled','set ASI enabled\nset ASI LOCALACK\nset ASI LOCALSTATUS')
    base='\n'.join(line for line in base.splitlines() if not line.startswith('expect -p'))+'\n'
    base=base.replace('EDSRC','NEWTXT')
    script=out/'check.ini';script.write_text(base)
    run=execute(Path('BIN/hp2100').resolve(),script,out/'check.log',600)
    files=read_volume(disk,3);text=console.read_text(errors='replace')
    saved=decode_text(files['NEWTXT'][1]) if 'NEWTXT' in files else None
    passed=run['status']=='PASS' and saved=='HELLO EDIT\n' and 'Insert text before current line' in text
    report=dict(status='PASS' if passed else 'FAIL',execution=run,saved=saved,
                host_ENQ_or_status_responders=False)
    (out/'results.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps(report,indent=2));return int(not passed)


if __name__=='__main__':raise SystemExit(main())
