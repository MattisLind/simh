"""Logged native XL LOADR operations on the staged archive working image."""
import argparse
import hashlib
import json
import re
from pathlib import Path
from rte_7920 import read_volume
from run_baseline import execute

OUT = Path('build/hp1000/rte-xl-archive')


def session(name, commands, budget=2000000000, disk=None):
    disk = disk or OUT / 'installation-7920.disc'
    base = Path('build/hp1000/rte-xl-7920')
    console = OUT / (name + '-console.txt')
    console.write_bytes(b'')
    prefix = (base / 'development.ini').read_text().split(':prompt0\n', 1)[0]
    prefix = prefix.replace(str((base / 'rte-xl-7920.disc').resolve()), str(disk.resolve())).replace(
        str((base / 'development-console.txt').resolve()), str(console.resolve()))
    prefix = prefix.replace('step 200000000', f'step {budget}')
    c = [prefix]
    for i, command in enumerate(commands):
        c += [f':prompt{i}', f'expect "FMGR : \\021" goto prompt{i+1}',
              f'send after=10000,delay=10000,"{command}\\r"', 'goto wait']
    c += [f':prompt{len(commands)}', 'noexpect', 'echo HP1000_CHECK_PASS', 'exit']
    script = OUT / (name + '.ini')
    script.write_text('\n'.join(c) + '\n')
    run = execute(Path('BIN/hp2100').resolve(), script, script.with_suffix('.log'), 1800)
    return run, console.read_text(errors='replace')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('phase', choices=['gate', 'edit', 'fortran', 'pascal', 'macro', 'fortran2', 'generator', 'image', 'fortran3', 'generator2'])
    parser.add_argument('--disk', type=Path, default=OUT / 'installation-7920.disc')
    args = parser.parse_args()
    phase = args.phase
    config = dict(gate=(3, 'RBCMD', ['RBGATE']), edit=(3,'EDCMD',['EDIT']),
        fortran=(4,'F4CMD',['FTN4X']), pascal=(5,'PASCMD',['PASCL','RASCL','PCL'] + [f'P{i:02}P' for i in range(1,13)] + ['PXREF','ALTER']),
        macro=(8,'MACCMD',['MAC140']), fortran2=(4,'F4ALT',['FTN4X']),
        generator=(0,'GNLOAD',['XLGEN']), generator2=(0,'GNLD2',['XLGEN']), fortran3=(4,'F4ORD',['FTN4X']),
        image=(9,'IMCMD',['DBDS','DBBLD','DBSTR','DBRST','DBULD','DBLOD','DBSPA','RECOV','DBCOP','QUERY']))
    volume, command, expected = config[phase]
    commands = [f'MC,{v+2}' for v in sorted({volume,6,7} if phase=='pascal' else {volume})]
    commands += [f'RU,LOADR,{command}::{32001+volume}']
    if phase == 'gate':
        commands += ['RU,RBGATE::32004']
    run, text = session(phase + '-load', commands, disk=args.disk)
    errors = re.findall(r'LOADR:[^\r\n]*(?:UN EXT|IL MRG|ABORTED|NM SEG|OV SYM|LM LIB|ER \d)[^\r\n]*', text)
    linked = {n: bool(re.search(r'LOADR:' + re.escape(n) + r'\s+READY', text)) for n in expected}
    files = read_volume(args.disk, 6 if phase=='pascal' else volume)
    artifacts = {n: dict(type=files[n][0],bytes=len(files[n][1]),sha256=hashlib.sha256(files[n][1]).hexdigest()) for n in expected if n in files}
    passed = run['status']=='PASS' and all(linked.values()) and not errors
    if phase=='gate': passed = passed and 'ASSEMBLY TEST PASSED' in text
    result = dict(status='PASS' if passed else 'FAIL', phase=phase, linked=linked, errors=errors,
        artifacts=artifacts, execution=run, functional_smoke_pass=(passed if phase=='gate' else False))
    (OUT / (phase + '-results.json')).write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps(result,indent=2))
    return int(not passed)


if __name__ == '__main__':
    raise SystemExit(main())
