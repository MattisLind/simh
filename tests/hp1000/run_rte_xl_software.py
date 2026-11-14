"""Install supplied HP language tools with the native XL loader on a working 7920.

Requires validated run_rte_xl_boot.py --disk 7920 and run_rte_xl_loader.py.
Distribution relocatables and libraries are copied unchanged; HP LOADR links them.
"""
import argparse
import hashlib
import json
import re
from pathlib import Path
from run_rte_xl_boot import payloads
from rte_7920 import make_image, read_volume
from rte_records import encode_text
from software_media import basic_media
from run_baseline import execute


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, default=Path('build/hp1000/rte-xl-software'))
    parser.add_argument('--trace', action='store_true')
    args = parser.parse_args()
    out = args.output
    out.mkdir(parents=True, exist_ok=True)
    base = Path('build/hp1000/rte-xl-7920')
    for result in [base / 'results.json', Path('build/hp1000/rte-xl-loader/results.json')]:
        if json.loads(result.read_text())['status'] != 'PASS':
            raise ValueError('boot and loader prerequisites must pass')
    files = payloads(base / 'rte-xl-7920.disc', '7920')
    files['LOADR'] = (6, Path('build/hp1000/rte-xl-loader/LOADR.bin').read_bytes())
    master2 = Path('hp1000-references/software/operating-systems/92071_RTE-XL_MasterDiscs_Rev2340/92071-13415_RTE-XL-2_REV2340.hpi')
    source_hash = hashlib.sha256(master2.read_bytes()).hexdigest()
    tools = payloads(master2)
    basic = basic_media()
    libraries = ['$SYSLB', '$FMP', '$DKLIB', '$CMDLB', '$MLIB1', '$MLIB2', '$MXLB', '$LDRLN']
    preamble = 'SZ,32\nSN,SNAP::32001\n' + ''.join(f'LI,{n}::32001\n' for n in libraries)
    macro_order = ['%MACRO', '%MACR0', '%MACR3', '%MACR7', '%MACR1', '%MACR2', '%MACR4', '%MACR5', '%MACR6']
    tools['MACCMD'] = (3, encode_text(preamble + 'OU,MACRO::32002\nSG,8\nSZ,32\n' +
        ''.join(f'RE,{n}::32002\n' for n in macro_order) + 'EN\n'))
    tools['FCCMD'] = (3, encode_text('SZ,32\nSN,SNAP::32001\n' + 'OU,FC::32002\nSG,7\nSZ,32\nOP,BP\n' +
        'LI,$FCL1::32002\nLI,$FCL2::32002\nLI,$PLIB::32001\n' +
        ''.join(f'LI,{n}::32001\n' for n in ['$SYSLB', '$FMP', '$DKLIB', '$MLIB1', '$MLIB2']) +
        ''.join(f'RE,{n}::32002\n' for n in ['%FCML'] + [f'%FC{i}' for i in range(7)]) + 'EN\n'))
    basic_libraries = ['$BSLBL', '$ABLIB']
    basic_preamble = 'SZ,32\nSN,SNAP::32001\n' + ''.join(
        f'LI,{n}::32003\n' for n in basic_libraries) + ''.join(
        f'LI,{n}::32001\n' for n in ['$SYSLB', '$FMP', '$DKLIB', '$MLIB1', '$MLIB2', '$MXLB'])
    basic['BSCMD'] = (3, encode_text(basic_preamble +
        'OU,BASIC::32003\nOP,CP\nRE,%BASIC::32003\nEN\n'))
    basic['BTCMD'] = (3, encode_text(basic_preamble +
        'OU,BATBL::32003\nOP,CP\nSG,2\nRE,%BATBL::32003\nEN\n'))
    disk = out / 'rte-xl-development-7920.disc'
    console = out / 'console.txt'
    console.write_bytes(b'')
    # Reuse the validated hardware/ROM setup, with independent media and console.
    prefix = (base / 'development.ini').read_text().split(':prompt0\n', 1)[0]
    prefix = prefix.replace('step 200000000', 'step 2000000000')
    prefix = prefix.replace(str((base / 'rte-xl-7920.disc').resolve()), str(disk.resolve())).replace(
        str((base / 'development-console.txt').resolve()), str(console.resolve()))
    commands = ['MC,3', 'MC,4', 'RU,LOADR,LDCMD::32002']
    # First validate native loader startup and its file-driven interface.
    tools_command = preamble + 'OU,DRTEST::32002\nRE,%D.RTR::32002\nEN\n'
    # D.RTR is on master 1; retain that original relocatable on the tool volume.
    master1 = master2.with_name('92071-13401_RTE-XL-1_REV2340.hpi')
    tools['%D.RTR'] = payloads(master1)['%D.RTR']
    tools['LDCMD'] = (3, encode_text(tools_command))
    layout = make_image(disk, {0: files, 1: tools, 2: basic})
    (out / 'layout.json').write_text(json.dumps(layout, indent=2) + '\n')
    commands += ['RU,LOADR,MACCMD::32002']
    commands += ['RU,LOADR,FCCMD::32002', 'RU,LOADR,BSCMD::32003', 'RU,LOADR,BTCMD::32003']
    if args.trace:
        prefix = prefix.replace('reset -p', f'set debug {(out / "io.trace").resolve()}\nset DA debug=rwsc\nset HPI debug=xfer\nreset -p')
        prefix = prefix.replace('exit AFAIL', 'ex HPI INHOLD,INCOUNT,OUTCOUNT,REMAIN,RECEIVING,ENDINPUT,DMAEN,REGS[16:31],CONTROL,PHI[0:7],FLAGS,CONTROLS\nex DA ISTATE[0],ICMD[0]\nsave ' + str((out / 'failed.sav').resolve()) + '\nexit AFAIL')
    c = [prefix]
    for i, command in enumerate(commands):
        c += [f':prompt{i}', f'expect "FMGR : \\021" goto prompt{i+1}',
              f'send after=10000,delay=10000,"{command}\\r"', 'goto wait']
    c += [f':prompt{len(commands)}', 'noexpect', 'echo HP1000_CHECK_PASS', 'exit']
    script = out / 'install.ini'
    script.write_text('\n'.join(c) + '\n')
    run = execute(Path('BIN/hp2100').resolve(), script, script.with_suffix('.log'), 1800)
    text = console.read_text(errors='replace')
    linked = {name: bool(re.search(r'LOADR:' + re.escape(name) + r'\s+READY', text))
              for name in ['DRTEST', 'MACRO', 'FC', 'BASIC', 'BATBL']}
    clean = not re.search(r'ABORTED|IL MRG|UN EXT|NM SEG|FMP ERROR|FMGR[- ]\d', text)
    unchanged = hashlib.sha256(master2.read_bytes()).hexdigest() == source_hash
    artifacts = {}
    for volume, names in [(1, ['DRTEST', 'MACRO', 'FC']), (2, ['BASIC', 'BATBL'])]:
        actual = read_volume(disk, volume)
        for name in names:
            if name in actual:
                kind, binary = actual[name]
                artifacts[name] = dict(type=kind, bytes=len(binary), sha256=hashlib.sha256(binary).hexdigest())
    result = dict(artifacts=artifacts, status='PASS' if run['status'] == 'PASS' and all(linked.values()) and clean and unchanged else 'FAIL',
                  linked=linked, run=run, image=str(disk), original_master_unchanged=unchanged,
                  language_execution_verified=False)
    (out / 'results.json').write_text(json.dumps(result, indent=2) + '\n')
    print(json.dumps(result, indent=2))
    return int(result['status'] != 'PASS')


if __name__ == '__main__':
    raise SystemExit(main())
