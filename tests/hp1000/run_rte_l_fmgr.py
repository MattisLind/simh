"""Build and validate a genuine disk-based RTE-L development floppy.

HP RTLGN generates SYSTEM/SNAP; the host LOADR links the RTE-L loader,
which uses SNAP to produce native FMGR, ASMB and LOADR memory-image files.
Only working copies are writable. No guest executable is patched.
"""
import argparse
import hashlib
import json
import re
import subprocess
import sys
from pathlib import Path

from rte_archive import saver_tape
from rte_disk import append_files, inspect
from rte_records import encode_text, decode_text
from run_baseline import execute
from run_rte_l_generation import host_files


LIBRARIES = ('$SYSLB', '$FMP', '$DKLIB', '$CMDLB', '$MLIB1', '$MLIB2',
             '$CLIBL', '$HPIB', '$MXLB', '$LDRLB')
HELLO = '''ASMB,R,L
      NAM HELLO,3,99
      EXT REIO,EXEC
HELLO LDA =D41
      ADA =D1
      CPA =D42
      JMP GOOD
      JMP BAD
GOOD  JSB REIO
      DEF *+5
      DEF TWO
      DEF ONE
      DEF MSG
      DEF LEN
      JMP DONE
BAD   JSB REIO
      DEF *+5
      DEF TWO
      DEF ONE
      DEF ERR
      DEF LEN
DONE  JSB EXEC
      DEF *+2
      DEF SIX
ONE   DEC 1
TWO   DEC 2
SIX   DEC 6
LEN   DEC -20
MSG   ASC 10,ASSEMBLY TEST PASSED
ERR   ASC 10,ASSEMBLY TEST FAILED
      END HELLO
'''
HELLO_LINK = '''SN,SNAP
LI,$SYSLB
LI,$FMP
LI,$MLIB1
LI,$MLIB2
LI,$MXLB
OU,HELLO
RE,HELOR
EN
'''


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def cross_link(simulator, generated):
    """Run original loaders on the generated IVB working host."""
    kit = Path('hp1000-references/software/operating-systems/RTE-IVB')
    master = Path('hp1000-references/software/operating-systems/92070-13401.hpi')
    links = []
    for command, relocatable, name in [('FMLINK', '%FMGR', 'FMGR'),
                                      ('ASLINK', '%ASMBC', 'ASMB'),
                                      ('LDLINK', '%LOADR', 'LOADR')]:
        text = 'SN,SNAP::SC\n' + ''.join(f'LI,{lib}::SC\n' for lib in LIBRARIES)
        text += f'OU,{name}::SC\nRE,{relocatable}::SC\nEN\n'
        links.append((command, 3, encode_text(text)))
        (generated / (command + '.txt')).write_text(text)
    tape = generated / 'cross-link.tap'
    manifest = saver_tape(master, tape, links, file_names=[])
    (generated / 'cross-link-manifest.json').write_text(json.dumps(manifest, indent=2) + '\n')
    config = (kit / 'RTE-IVB.sim').read_text().rsplit('boot DA0', 1)[0]
    config = config.replace('set CPU IDLE', 'set CPU NOIDLE').replace(
        'attach DA0 RTE-IVB-SYSTEM.U0.7920H.disc',
        f'attach DA0 {(generated / "host.disc").resolve()}')
    commands = ['set on', 'on error exit 1', config,
                f'attach -r MSC0 {tape.resolve()}', 'runlimit 10000000',
                'on error ignore', 'boot DA0', 'norunlimit',
                'send after=10000,delay=10000,"\\r"', 'step 1000000']

    def send(text, count=10000000):
        commands.extend([f'send "{text}\\r"', f'step {count}'])

    send('RU,FMGR')
    for text in ['RU,READR', 'OC,SC', 'AL', 'EN', 'AB', 'RU,LOADR',
                 'SZ,24', 'LI,$LDRLB::SC', 'LI,$MXLB::SC']:
        send(text)
    send(r'RE,\045LOADR::SC', 200000000)
    send('EN', 30000000)
    # The original IVB loader deliberately renames a duplicate LOADR to
    # ..ADR. This leaves the host's installed LOADR intact.
    for command, _, _ in links:
        send(f'RU,..ADR,{command}::SC', 600000000)
    commands.extend(['echo HP1000_CHECK_PASS', 'exit'])
    script = generated / 'cross-link.ini'
    script.write_text('\n'.join(commands) + '\n')
    result = execute(simulator, script, script.with_suffix('.log'), 600)
    transcript = script.with_suffix('.log').read_text(errors='replace')
    if result['status'] != 'PASS' or any(
            not re.search(rf'\.\.ADR:{name}\s+READY', transcript)
            for name in ['FMGR', 'ASMB', 'LOADR']):
        raise RuntimeError('original cross-loader did not produce all three programs')
    if re.search(r'ABORTED|OP CODE ERR|UN EXT|IL REC', transcript):
        raise RuntimeError('cross-loader reported an error')
    programs = host_files(generated / 'host.disc', ['FMGR', 'ASMB', 'LOADR'])
    for name, (kind, payload) in programs.items():
        if kind != 6:
            raise ValueError(f'{name} is not a native type-6 memory-image file')
        (generated / (name + '.bin')).write_bytes(payload)
    provenance = dict(execution=result, SNAP_sha256=digest(generated / 'SNAP.bin'),
                      programs={name: dict(type=kind, bytes=len(payload),
                                sha256=hashlib.sha256(payload).hexdigest())
                                for name, (kind, payload) in programs.items()})
    (generated / 'programs.json').write_text(json.dumps(provenance, indent=2) + '\n')
    return programs


def session(simulator, generated, image, output, name, operations):
    """Fresh firmware boot, then type real FMGR commands through the ASI."""
    raw = image.read_bytes()
    directory = inspect(image)
    entry = next(e for e in directory['files'] if e['name'] == 'SYSTEM')
    system = raw[entry['offset']:entry['offset'] + entry['bytes']]
    console = output / (name + '-console.txt')
    console.write_bytes(b'')
    commands = ['set on', 'on error exit 1', 'set cpu 1000-L',
                'set ASI enabled', 'set HPI enabled',
                f'set cpu LROM={(generated / "rom.bin").resolve()}',
                f'attach HPI0 {image.resolve()}', f'attach ASI {console.resolve()}',
                'deposit S 400', 'reset -p', 'on error ignore', 'step 50000000',
                'on error exit 1', 'assert LSTATUS=207', 'break 2003',
                'send "\\045BDC27\\r"', 'on error ignore', 'step 30000000',
                'on error exit 1', 'assert P=2003', 'assert LROMEN=0']
    commands += [f'assert {a:o}={int.from_bytes(system[a*2:a*2+2], "big"):o}'
                 for a in range(2, 0o76000)]
    commands += ['nobreak 2003',
                 r'expect -p "\005" send after=100,delay=100,"\006"; goto wait',
                 'expect "FMGR : " goto prompt0', ':wait', 'on error ignore',
                 'step 10000000', 'on error exit 1', 'exit AFAIL']
    for index, operation in enumerate(operations):
        commands += [f':prompt{index}', f'expect "FMGR : " goto prompt{index+1}',
                     f'send after=10000,delay=10000,"{operation}\\r"', 'goto wait']
    commands += [f':prompt{len(operations)}', 'noexpect',
                 'echo HP1000_CHECK_PASS', 'exit']
    script = output / (name + '.ini')
    script.write_text('\n'.join(commands) + '\n')
    result = execute(simulator, script, script.with_suffix('.log'), 180)
    text = console.read_text(errors='replace')
    if result['status'] != 'PASS' or '*RTE-L SYSTEM READY*' not in text:
        raise RuntimeError(f'{name}: firmware/FMGR session failed')
    if re.search(r'I/O-TO|ABORTED|FMGR-\d|FMGR [+-]?\d', text):
        raise RuntimeError(f'{name}: guest reported a disk or program error')
    return result, text


def file_payload(image, name):
    directory = inspect(image)
    entry = next(e for e in directory['files'] if e['name'] == name)
    return entry, image.read_bytes()[entry['offset']:entry['offset'] + entry['bytes']]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--simulator', type=Path, default=Path('BIN/hp2100'))
    parser.add_argument('--output', type=Path, default=Path('build/hp1000/rte-l-fmgr'))
    parser.add_argument('--generated', type=Path,
                        default=Path('build/hp1000/rte-l-fmgr-generated'))
    parser.add_argument('--reuse-build', action='store_true',
                        help='reuse this runner\'s recorded generator and cross-loader outputs')
    args = parser.parse_args()
    out, generated = args.output, args.generated
    out.mkdir(parents=True, exist_ok=True)
    simulator = args.simulator.resolve()
    sources = [Path('hp1000-references/software/operating-systems/92070-13401.hpi'),
               Path('hp1000-references/software/operating-systems/RTE-IVB/RTE-IVB-SYSTEM.U0.7920H.disc')]
    original_hashes = {str(p): digest(p) for p in sources}
    if not args.reuse_build:
        generation = subprocess.run([sys.executable, 'tests/hp1000/run_rte_l_generation.py',
                    '--simulator', str(simulator), '--output', str(generated),
                    '--commands', 'tests/hp1000/config/rte-l-7902-fmgr.gen',
                    '--generation-instructions', '400000000'],
                    stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
        (out / 'generation-result.log').write_text(generation.stdout)
        if generation.returncode:
            raise RuntimeError('RTLGN failed; inspect generation-result.log')
        programs = cross_link(simulator, generated)
    else:
        provenance = json.loads((generated / 'programs.json').read_text())
        if provenance['SNAP_sha256'] != digest(generated / 'SNAP.bin'):
            raise ValueError('cached programs do not match the generated SNAP')
        programs = {name: (6, (generated / (name + '.bin')).read_bytes())
                    for name in ['FMGR', 'ASMB', 'LOADR']}
        if any(hashlib.sha256(payload).hexdigest() != provenance['programs'][name]['sha256']
               for name, (_, payload) in programs.items()):
            raise ValueError('cached native program changed')
    image = out / 'rte-l-development-7902.hpi'
    additions = [(name, *programs[name]) for name in ['FMGR', 'ASMB', 'LOADR']]
    # START transfers to WELCOM. An empty command file returns normally
    # to interactive FMGR without depending on optional welcome commands.
    additions += [('WELCOM', 3, encode_text('')),
                  ('HELOS', 3, encode_text(HELLO)), ('HLDCMD', 3, encode_text(HELLO_LINK))]
    installed = append_files(generated / 'rte-l-7902.hpi', image, additions)
    (out / 'installed-directory.json').write_text(json.dumps(installed, indent=2) + '\n')
    first, text = session(simulator, generated, image, out, 'development',
                         ['DL', 'ST,HELOS,COPY,AS', 'RU,ASMB,HELOS,HLIST,HELOR',
                          'RU,LOADR,HLDCMD', 'RU,HELLO'])
    if ('NO ERRORS TOTAL' not in text or 'LOADR:HELLO  READY' not in text
            or 'ASSEMBLY TEST PASSED' not in text or 'ASSEMBLY TEST FAILED' in text):
        raise RuntimeError('native assembly/link/execution did not pass')
    _, copy = file_payload(image, 'COPY')
    if decode_text(copy) != HELLO:
        raise RuntimeError('FMGR stored source text differs from its input')
    saved = {name: file_payload(image, name)[0]['sha256']
             for name in ['COPY', 'HELOR', 'HLIST', 'HELLO']}
    second, text = session(simulator, generated, image, out, 'reboot',
                          ['RU,HELLO', 'DU,COPY,1,AS'])
    if 'ASSEMBLY TEST PASSED' not in text or 'NAM HELLO,3,99' not in text:
        raise RuntimeError('fresh boot did not execute/read the persistent files')
    if decode_text(file_payload(image, 'COPY')[1]) != HELLO or any(
            file_payload(image, name)[0]['sha256'] != checksum for name, checksum in saved.items()):
        raise RuntimeError('persistent files changed across the fresh boot')
    cleanup, text = session(simulator, generated, image, out, 'file-operations',
                            ['ST,COPY,TEMP,AS', 'RN,TEMP,RENAM',
                             'DU,RENAM,1,AS', 'PU,RENAM'])
    if 'NAM HELLO,3,99' not in text or any(
            e['name'] in ('TEMP', 'RENAM') for e in inspect(image)['files']):
        raise RuntimeError('FMGR create/rename/read/purge did not complete')
    final_directory = {e['name']: e for e in inspect(image)['files']}
    if any(final_directory[e['name']]['sha256'] != e['sha256']
           for e in inspect(sources[0])['files']):
        raise RuntimeError('guest disk operations changed an original distribution file')
    unchanged = all(digest(Path(p)) == checksum for p, checksum in original_hashes.items())
    if not unchanged:
        raise RuntimeError('an original source medium changed')
    result = dict(status='PASS', disk_based_FMGR=True, native_ASMB=True, native_LOADR=True,
                  arithmetic_program_executed=True, persistent_files=saved,
                  fresh_boot_read_and_execution=True, software_patched=False,
                  original_sources_unchanged=unchanged, sources=original_hashes,
                  image=str(image), image_sha256=digest(image),
                  generation=str(generated / 'results.json'), first=first, reboot=second,
                  create_rename_read_purge=cleanup, distribution_payloads_unchanged=True,
                  next='XL memory management investigation; no ALGOL or chess dependency')
    (out / 'results.json').write_text(json.dumps(result, indent=2) + '\n')
    print(json.dumps(result, indent=2))


if __name__ == '__main__':
    main()
