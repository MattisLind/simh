"""Inventory and stage official archive packages on a separate XL 7920 image."""
import hashlib
import json
import re
import subprocess
import zipfile
from pathlib import Path
from rte_rbin import encode, decode
from rte_records import encode_text
from rte_7920 import make_image, read_volume
from run_rte_xl_boot import payloads

ROOT = Path('hp1000-references/software/diagnostics/archives')
OUT = Path('build/hp1000/rte-xl-archive')


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    archive = ROOT / 'type-5.zip'
    source = Path('build/hp1000/rte-xl-languages/rte-xl-languages-7920.disc')
    if json.loads((source.parent / 'results.json').read_text())['status'] != 'PASS':
        raise ValueError('verified XL language image required')
    manifest = dict(commit=subprocess.check_output(['git', 'rev-parse', 'HEAD'], text=True).strip(),
        source_image=str(source), source_sha256=hashlib.sha256(source.read_bytes()).hexdigest(),
        archive=str(archive), archive_sha256=hashlib.sha256(archive.read_bytes()).hexdigest(),
        files=[], missing=[], sources={})
    volumes = {i: read_volume(source, i) for i in range(3)}
    volumes.update({i: {} for i in range(3, 10)})
    def text(part, volume, name):
        path = ROOT / 'type-4' / (part + '.src')
        raw = path.read_bytes()
        manifest['sources'][str(path)] = hashlib.sha256(raw).hexdigest()
        content = raw.decode('ascii').replace('\r\n', '\n')
        volumes[volume][name] = (4, encode_text(content))
        return content
    with zipfile.ZipFile(archive) as z:
        def binary(part, volume, name):
            member = 'type-5/' + part + '.rbin'
            if member not in z.namelist():
                manifest['missing'].append(member)
                return
            raw = z.read(member)
            data, info = encode(raw)
            volumes[volume][name] = (5, data)
            manifest['files'].append(dict(member=member, name=name, type=5,
                cartridge=32001 + volume, bytes=len(data), **info))
        for i, name in enumerate(['%EDITA', '%EDITB', '$ED1K4', '$ED1KL', '$ED1K6'], 1):
            binary(f'92074-1200{i}_Rev-2140', 3, name)
        edit = text('92074-17002_Rev-2140', 3, '#ED1KL')
        text('92074-17004_Rev-2140', 3, '"EDIT.')
        adapted = 'SN,SNAP::32001\nOU,EDIT::32004\n' + edit.replace('LIB,$ED1KL', 'LIB,$ED1KL::32004').replace('RE,%EDITA', 'RE,%EDITA::32004').replace('RE,%EDITB', 'RE,%EDITB::32004')
        volumes[3]['EDCMD'] = (3, encode_text(adapted))
        for part, name in [('12001', '$F4XCS'), ('16002', '%F4X1'), ('16003', '%F4X2')]:
            binary(f'92834-{part}_Rev-2226', 4, name)
        ft = text('92834-17002_Rev-2226', 4, '#FTN4X')
        text('92834-17001_Rev-2226', 4, '"FTN4X')
        text('92834-17999_Rev-2226', 4, 'A92834')
        # The source explicitly requires SG7 on XL. FCLBL is the installed
        # XL file-access library. This initial candidate is retained for
        # evidence; F4ORD from adjust_rte_xl_archive_loads.py is the
        # verified recipe with CLIBL after the common compiler library.
        adapted = 'SN,SNAP::32001\nOU,FTN4X::32005\nSG,7\nLI,$FCLBL::32001\n' + ft.replace('LI,$F4XCS', 'LI,$F4XCS::32005').replace('RE,%F4X1', 'RE,%F4X1::32005').replace('RE,%F4X2', 'RE,%F4X2::32005')
        volumes[4]['F4CMD'] = (3, encode_text(adapted))
        catalog = text('92854-17999_Rev-2144', 5, 'A92854')
        for line in catalog.splitlines():
            match = re.match(r'\s*(\S+)\s+(92854-16\d{3})\s+(2144)\s+R\s', line)
            if match:
                name, part, rev = match.groups()
                binary(part + '_Rev-' + rev, 5, name)
        for part, name in [('17001','*LOAD'),('17002','#PAS'),('17003','#PANS'),('17004','"PERRS'),('17005',')ALTER')]:
            content = text('92854-' + part + '_Rev-2144', 5, name)
            if name == '#PAS':
                adapted = content
                for alias, cr in [('PX',32006),('MS',32001),('XP',32007),('LL',32008),('SY',32001)]:
                    adapted = adapted.replace('::' + alias, '::' + str(cr))
                volumes[5]['PASCMD'] = (3, encode_text(adapted))
        volumes[6]['SNAP'] = volumes[0]['SNAP']
        # Preserve the already verified Rev.2340 assembler on volume 1.
        for i, name in enumerate(['%MACRO','%MACR0','%MACR1','%MACR2','%MACR3','%MACR4','%MACR5','%MACR6','%MACR7'], 1):
            binary(f'92059-160{i:02d}_Rev-2140', 8, name)
        text('92059-17001_Rev-2140', 8, '#MACRO')
        text('92059-17003_Rev-2326', 8, '"MACRO')
        commands = 'SN,SNAP::32001\nOU,MAC140::32009\nSG,8\nSZ,32\n' + ''.join('LI,' + name + '::32001\n' for name in ['$SYSLB','$FMP','$DKLIB','$CMDLB','$MLIB1','$MLIB2','$MXLB'])
        commands += ''.join('RE,' + name + '::32009\n' for name in ['%MACRO','%MACR0','%MACR3','%MACR7','%MACR1','%MACR2','%MACR4','%MACR5','%MACR6']) + 'EN\n'
        volumes[8]['MACCMD'] = (3, encode_text(commands))
        # Gate the record transport with a known working small object, not
        # execution of a service routine with an invalid standalone ABI.
        raw = decode(volumes[1]['ASMOBJ'][1])
        wrapped, info = encode(raw)
        volumes[3]['RBSMAL'] = (5, wrapped)
        gate = 'SN,SNAP::32001\n' + ''.join('LI,' + n + '::32001\n' for n in ['$SYSLB','$FMP','$MLIB1','$MLIB2','$MXLB']) + 'OU,RBGATE::32004\nRE,RBSMAL::32004\nEN\n'
        volumes[3]['RBCMD'] = (3, encode_text(gate))
        manifest['transport_smoke_object'] = info
        # Independently compare import envelopes with the same official
        # Rev.2340 bytes already shipped in the XL master disk.
        master = Path('hp1000-references/software/operating-systems/92071_RTE-XL_MasterDiscs_Rev2340/92071-13415_RTE-XL-2_REV2340.hpi')
        official = payloads(master)['%EDITA'][1]
        raw = z.read('type-5/92074-12001_Rev-2340.rbin')
        converted, _ = encode(raw)
        from rte_rbin import records
        used = len(raw) + 4 * len(records(raw)) + 2
        manifest['official_master_record_equivalence'] = decode(official) == raw and converted[:used] == official[:used]
        manifest['master_allocation_padding_identical'] = converted[used:] == official[used:]
        if not manifest['official_master_record_equivalence']:
            raise ValueError('archive transport differs from official master file')
        manifest['image_92073_members'] = [n for n in z.namelist() if '/92073-' in n]
    image = OUT / 'installation-7920.disc'
    manifest['layout'] = make_image(image, volumes)
    manifest['image'] = str(image)
    (OUT / 'inventory.json').write_text(json.dumps(manifest, indent=2) + '\n')
    print(json.dumps(dict(files=len(manifest['files']), missing=manifest['missing'],
        official_master_record_equivalence=manifest['official_master_record_equivalence'], image=str(image)), indent=2))


if __name__ == '__main__':
    main()
