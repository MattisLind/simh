"""Install the zero-error #PANS generation on a separate 7920 working copy."""
import json
import argparse
from pathlib import Path
from rte_7920 import read_volume, make_image
from rte_xl_boot import install_parameters
from run_rte_xl_boot import payloads
from run_rte_xl_archive import OUT, session


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--line-console-only',action='store_true')
    args=parser.parse_args()
    stem='line' if args.line_console_only else 'pascal'
    generated=Path(f'build/hp1000/rte-xl-{stem}-generated')
    if json.loads((generated/'results.json').read_text())['status']!='PASS':
        raise ValueError('zero-error Pascal system generation required')
    source=OUT/'installation-7920.disc'
    volumes={v:read_volume(source,v) for v in range(10)}
    system=(generated/'SYSTEM.bin').read_bytes()
    snapshot=(generated/'SNAP.bin').read_bytes()
    master=Path('hp1000-references/software/operating-systems/92071_RTE-XL_MasterDiscs_Rev2340/92071-13401_RTE-XL-1_REV2340.hpi')
    boot,installation=install_parameters(payloads(master)['BOOTEX'][1],system,snapshot,2)
    # A system snapshot is HP file type 3, despite its binary records;
    # original BOOTEX explicitly rejects other file types.
    volumes[0].update(SYSTEM=(1,system),SNAP=(3,snapshot),BOOTEX=(1,boot))
    volumes[6]['SNAP']=(3,snapshot)
    disk=OUT/f'{stem}-system-7920.disc';make_image(disk,volumes)
    run,text=session(f'{stem}-system-boot',['DL'],disk=disk)
    result=dict(status=run['status'],execution=run,installation=installation,
                system_bytes=len(system),disk=str(disk))
    (OUT/f'{stem}-system-boot-results.json').write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps(result,indent=2))
    return int(run['status']!='PASS')


if __name__=='__main__':raise SystemExit(main())
