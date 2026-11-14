"""Compile/link/run assembly and exercise BASIC on the installed XL 7920."""
import json
import re
from pathlib import Path
from rte_7920 import make_image, read_volume
from rte_records import encode_text
from run_rte_l_fmgr import HELLO
from run_baseline import execute


def main():
    base = Path('build/hp1000/rte-xl-7920')
    installed = Path('build/hp1000/rte-xl-software')
    if json.loads((installed / 'results.json').read_text())['status'] != 'PASS':
        raise ValueError('native software installation must pass first')
    out = Path('build/hp1000/rte-xl-languages')
    out.mkdir(parents=True, exist_ok=True)
    source = installed / 'rte-xl-development-7920.disc'
    volumes = {i: read_volume(source, i) for i in range(3)}
    volumes[1]['&ASM'] = (3, encode_text(HELLO.replace('ASMB,R,L', 'MACRO,R,L')))
    command = 'SN,SNAP::32001\n' + ''.join(f'LI,{n}::32001\n' for n in
        ['$SYSLB', '$FMP', '$MLIB1', '$MLIB2', '$MXLB'])
    volumes[1]['ASMCMD'] = (3, encode_text(command + 'OU,HELLO::32002\nRE,ASMOBJ::32002\nEN\n'))
    disk = out / 'rte-xl-languages-7920.disc'
    make_image(disk, volumes)
    console = out / 'console.txt'
    console.write_bytes(b'')
    prefix = (base / 'development.ini').read_text().split(':prompt0\n', 1)[0]
    prefix = prefix.replace(str((base / 'rte-xl-7920.disc').resolve()), str(disk.resolve())).replace(
        str((base / 'development-console.txt').resolve()), str(console.resolve())).replace('step 200000000', 'step 2000000000')
    commands = ['MC,3', 'MC,4', 'RU,MACRO::32002,&ASM::32002,ASMLST::32002,ASMOBJ::32002',
                'RU,LOADR,ASMCMD::32002', 'RU,HELLO::32002', 'RU,BATBL::32003,*TBFIL::32003,1']
    c = [prefix]
    for i, command in enumerate(commands):
        c += [f':prompt{i}', f'expect "FMGR : \\021" goto prompt{i+1}',
              f'send after=10000,delay=10000,"{command}\\r"', 'goto wait']
    c += [f':prompt{len(commands)}', 'expect ">\\021" goto basic',
          r'send after=10000,delay=10000,"RU,BASIC::32003\r"', 'goto wait',
          ':basic', 'expect ">\\021" goto line20',
          r'send after=100000,delay=100000,"10 PRINT 6*7\r"', 'goto wait',
          ':line20', 'expect ">\\021" goto runbasic',
          r'send after=100000,delay=100000,"20 END\r"', 'goto wait',
          ':runbasic', 'expect ">\\021" goto arithmetic',
          r'send after=100000,delay=100000,"RUN\r"', 'goto wait',
          ':arithmetic', 'expect "FMGR : \\021" goto done',
          r'send after=10000,delay=10000,"BYE\r"', 'goto wait',
          ':done', 'noexpect', 'echo HP1000_CHECK_PASS', 'exit']
    script = out / 'languages.ini'
    script.write_text('\n'.join(c) + '\n')
    run = execute(Path('BIN/hp2100').resolve(), script, script.with_suffix('.log'), 1200)
    text = console.read_text(errors='replace')
    assembly = 'ASSEMBLY TEST PASSED' in text and 'ASSEMBLY TEST FAILED' not in text
    basic = 'BASIC READY' in text and bool(re.search(r'(?:^|[\r\n])[ \t]*42[ \t]*(?:[\r\n]|$)', text.replace('\x05', '')))
    clean = not re.search(r'ABORTED|UN EXT|IL MRG|I/O-TO|FMP ERROR|FMGR[- ]\d', text)
    result = dict(status='PASS' if run['status'] == 'PASS' and assembly and basic and clean else 'FAIL',
                  native_assembly=assembly, native_BASIC_arithmetic=basic, run=run, image=str(disk))
    (out / 'results.json').write_text(json.dumps(result, indent=2) + '\n')
    print(json.dumps(result, indent=2))
    return int(result['status'] != 'PASS')


if __name__ == '__main__':
    raise SystemExit(main())
