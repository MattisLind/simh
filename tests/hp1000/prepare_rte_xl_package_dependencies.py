"""Add catalog-proven dependencies and Pascal system-generation inputs.

Run after initial load attempts finish; this repacks only the dedicated working
installation image and preserves every existing file's bytes and type.
"""
import hashlib
import json
import re
import zipfile
from pathlib import Path
from rte_7920 import make_image, read_volume
from rte_rbin import encode, records, decode
from rte_records import encode_text
from run_rte_xl_boot import payloads
from stage_rte_xl_archive import OUT, ROOT


def main():
    disk=OUT/'installation-7920.disc'
    volumes={i:read_volume(disk,i) for i in range(10)}
    report=dict(inputs={},image_catalogs={})
    master=Path('hp1000-references/software/operating-systems/92071_RTE-XL_MasterDiscs_Rev2340/92071-13401_RTE-XL-1_REV2340.hpi')
    original=payloads(master)
    for name,value in original.items():volumes[0].setdefault(name,value)
    report['inputs'][str(master)]=hashlib.sha256(master.read_bytes()).hexdigest()
    with zipfile.ZipFile(ROOT/'type-5.zip') as z:
        part='type-5/92070-12009_Rev-2140.rbin'
        data,info=encode(z.read(part));volumes[4]['$CLIBL']=(5,data);report['CLIBL']=dict(member=part,**info)
    original_ft=(ROOT/'type-4/92834-17002_Rev-2226.src').read_text()
    ft='SN,SNAP::32001\nOU,FTN4X::32005\nSG,7\nLI,$CLIBL::32005\n'+original_ft.replace('LI,$F4XCS','LI,$F4XCS::32005').replace('RE,%F4X1','RE,%F4X1::32005').replace('RE,%F4X2','RE,%F4X2::32005')
    volumes[4]['F4ALT']=(3,encode_text(ft))
    link='SN,SNAP::32001\n'+''.join(f'LI,{n}::32001\n' for n in ['$SYSLB','$FMP','$DKLIB','$CMDLB','$MLIB1','$MLIB2','$MXLB'])+'OU,XLGEN::32001\nSG,4\nSZ,32\nRE,%RTLGN::32001\nEN\n'
    volumes[0]['GNLOAD']=(3,encode_text(link))
    commands=Path('tests/hp1000/config/rte-xl-7920.gen').read_text().replace('::SC','::32001')
    insert=[]
    for line in (ROOT/'type-4/92854-17003_Rev-2144.src').read_text().splitlines():
        line=line.strip()
        if not line or line.startswith('*'):continue
        line=line.replace('::PX','::32001' if line.startswith('MS,') else '::32006')
        insert.append(line)
    commands=commands.replace('SE,$SYS..::32001\n','\n'.join(insert)+'\nSE,$SYS..::32001\n',1)
    volumes[6]['PASGEN']=(3,encode_text(commands))
    (OUT/'pascal-system.gen').write_text(commands)
    image_source=Path('hp1000-references/software/operating-systems/92069-13404_IMAGEDUALFLEX_REV2226.hpi')
    image_files=payloads(image_source)
    # 92073A's own Rev.2226 catalog explicitly maps IMAGE/L to these
    # 92069 parts and to #IMAGL. Product-number absence is not a blocker.
    catalog=(ROOT/'type-4/92073-18999_Rev-2226.src').read_text()
    matched=[]
    for line in catalog.splitlines():
        match=re.match(r'\s*(\S+)\s+(92069-\d{5})\s+(\d{4})\s+R\s',line)
        if match:
            name,part,revision=match.groups()
            if name not in image_files:raise ValueError('IMAGE/L catalog file missing: '+name)
            raw=decode(image_files[name][1])
            # Confirm the requested part/revision in the component's own
            # records; old submodules within an official composite are valid.
            identity=(part+' REV.'+revision).encode()
            if identity not in raw and name != '*DBUP':
                raise ValueError('IMAGE/L component identity mismatch: '+name)
            # The catalog's *DBUP is a composite: its contained program
            # identifies 92069-16130 Rev.2140, not the catalog container 12001.
            if name == '*DBUP' and b'92069-16130 REV.2140' not in raw:
                raise ValueError('DBUP composite identity mismatch')
            matched.append(dict(name=name,part=part,revision=revision))
    volumes[9].update(image_files)
    volumes[9]['A92073']=(4,encode_text(catalog))
    report['image_catalogs']['2226']=matched
    report['inputs'][str(image_source)]=hashlib.sha256(image_source.read_bytes()).hexdigest()
    for path in sorted((ROOT/'type-4').glob('92073-18999_Rev-*.src')):
        entries=[]
        for line in path.read_text().splitlines():
            m=re.match(r'\s*(\S+)\s+(920\d\d-\d{5})\s+(\d{4})\s+([45RS])\s+(.*)',line)
            if m:entries.append(dict(zip(['name','part','revision','type','description'],m.groups())))
        report['image_catalogs'][path.stem]=entries
    # Follow the supplied #IMAGL's L/XL procedure, keeping the original.
    from rte_records import decode_text
    image_commands=decode_text(image_files['#IMAGL'][1])
    adapted=[]
    for line in image_commands.splitlines():
        text=line.strip()
        if text.startswith('SNAP,'):line='SN,SNAP::32001'
        elif text.startswith('OUTPUT,'):line=text+'::32010'
        elif text.startswith(('LIBRARY,','REL,')):
            name=text.split(',')[1].strip()
            line=text+('::32010' if name in image_files else '::32001')
        adapted.append(line)
    volumes[9]['IMCMD']=(3,encode_text('\n'.join(adapted)+'\n'))
    layout=make_image(disk,volumes)
    report['layout']=layout
    # Repacking retains complete logical payloads even for files whose old
    # allocation padding contained unrelated bytes after EOF.
    for v,files in volumes.items():
        if read_volume(disk,v)!=files:raise ValueError('repack changed file payloads')
    (OUT/'dependency-staging.json').write_text(json.dumps(report,indent=2)+'\n')
    print('Staged CLIBL2140, native XL generator, Pascal gen inserts and catalog-confirmed IMAGE/L2226')


if __name__=='__main__':main()
