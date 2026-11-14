"""Preserve functionally verified applications on a fresh combined 7920 copy."""
import hashlib
import json
from rte_7920 import read_volume,make_image
from run_rte_xl_archive import OUT,session


def main():
    for package in ['edit','fortran','macro']:
        if json.loads((OUT/f'{package}-smoke-results.json').read_text())['status']!='PASS':
            raise ValueError(f'{package} has not passed functional acceptance')
    source=OUT/'installation-7920.disc'
    volumes={v:read_volume(source,v) for v in range(10)}
    for v,package in [(1,'macro'),(3,'edit'),(4,'fortran')]:
        volumes[v]=read_volume(OUT/f'{package}-smoke.disc',v)
    # Linked IMAGE utilities are preserved, but are not marked database-tested.
    volumes[9]=read_volume(OUT/'image-load.disc',9)
    disk=OUT/'rte-xl-software-7920.disc';make_image(disk,volumes)
    commands=['MC,3','MC,5','MC,6','RU,FTEST::32005','RU,FRTEST::32005','RU,MCPLN::32002','RU,MCMAC::32002']
    run,text=session('combined-software',commands,disk=disk)
    passed=run['status']=='PASS' and 'FORTRAN REBOOT TEST PASSED' in text and text.count('ASSEMBLY TEST PASSED')==2 and 'ABORTED' not in text
    result=dict(status='PASS' if passed else 'FAIL',execution=run,disk=str(disk),
                sha256=hashlib.sha256(disk.read_bytes()).hexdigest(),
                accepted=['EDIT 2140','FTN4X 2226','MACRO 2340'],
                linked_only=['IMAGE/L utilities'],pascal_accepted=False)
    (OUT/'combined-results.json').write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps(result,indent=2));return int(not passed)


if __name__=='__main__':raise SystemExit(main())
