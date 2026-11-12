"""Boot the supplied IVB host, import original L relocatables, link/start RTLGN.

Uses a fresh byte-swapped working disc and HP's real READR and LOADR utilities.
This checks generator startup; it does not generate or claim a bootable SYSTEM.
"""
import argparse
import hashlib
import json
from pathlib import Path
from rte_archive import saver_tape
from run_baseline import execute


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--simulator', type=Path, default=Path('BIN/hp2100'))
    parser.add_argument('--kit', type=Path, default=Path('hp1000-references/software/operating-systems/RTE-IVB'))
    parser.add_argument('--master', type=Path, default=Path('hp1000-references/software/operating-systems/92070-13401.hpi'))
    parser.add_argument('--output', type=Path, default=Path('build/hp1000/rte-ivb-validation'))
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    source = args.kit / 'RTE-IVB-SYSTEM.U0.7920H.disc'
    data = source.read_bytes()
    source_hash = hashlib.sha256(data).hexdigest()
    if len(data) != 48 * 5 * 823 * 128 * 2:
        raise ValueError('unexpected 7920H image geometry')
    swapped = bytearray(len(data))
    swapped[::2], swapped[1::2] = data[1::2], data[::2]
    working = args.output / 'RTE-IVB-SIMH.disc'
    working.write_bytes(swapped)
    provenance = dict(source=str(source), sha256=source_hash, bytes=len(data),
                      working_copy=str(working), initial_swapped_sha256=hashlib.sha256(swapped).hexdigest())
    (args.output / 'provenance.json').write_text(json.dumps(provenance, indent=2) + '\n')
    tape = args.output / 'rte-l-import.tap'
    manifest = saver_tape(args.master, tape)
    (args.output / 'import-manifest.json').write_text(json.dumps(manifest, indent=2) + '\n')
    config = (args.kit / 'RTE-IVB.sim').read_text()
    before, boot = config.rsplit('boot DA0', 1)
    if boot.strip():
        raise ValueError('unexpected commands after packaged BOOT')
    before = before.replace('set CPU IDLE', 'set CPU NOIDLE')
    before = before.replace('attach DA0 RTE-IVB-SYSTEM.U0.7920H.disc',
                            f'attach DA0 {working.resolve()}')
    commands = [f'attach -r MSC0 {tape.resolve()}', 'runlimit 10000000',
                'on error ignore', 'boot DA0', 'norunlimit', 'on error exit 1',
                'send after=10000,delay=10000,"\\r"']

    def step(count):
        commands.extend(['on error ignore', f'step {count}', 'on error exit 1'])

    def send(text, count):
        commands.append(f'send "{text}\\r"')
        step(count)

    step(1000000)
    send('RU,FMGR', 3000000)
    send('CL', 3000000)
    send('RU,READR', 3000000)
    send('OC,SC', 2000000)
    send('AL', 1000000)
    send('EN', 70000000)
    send('AB', 2000000)
    send('RU,LOADR', 3000000)
    send('LI,$LDRLB::SC', 2000000)
    send('LI,$MXLB::SC', 2000000)
    send('RE,\\045RTLGN::SC', 200000000)
    send('EN', 30000000)
    send('RU,RTLGN', 10000000)
    commands += ['echo HP1000_CHECK_PASS', 'exit']
    script = args.output / 'host-generator.ini'
    script.write_text('set on\non error exit 1\n' + before + '\n' + '\n'.join(commands) + '\n')
    log = script.with_suffix('.log')
    result = execute(args.simulator.resolve(), script, log, 180)
    transcript = log.read_text(errors='replace')
    checks = dict(host_boot='THE RTE-IVB SYSTEM IS UP AND RUNNING.' in transcript,
                  all_files_restored=transcript.count('Restore ') == len(manifest['files']),
                  all_files_verified=transcript.count('Verify ') == len(manifest['files']),
                  generator_linked='RTLGN  READY AT' in transcript and 'LOADR ABORTED' not in transcript,
                  generator_started='FMGR -6  ON FILE  COMAND' in transcript,
                  source_unchanged=hashlib.sha256(source.read_bytes()).hexdigest() == source_hash)
    if not all(checks.values()):
        result['status'] = 'FAIL'
    result.update(checks=checks, generation_complete=False, RTE_L_running=False,
                  next_requirement='A validated RTE-L generator command/answer file and complete system-generation validation')
    (args.output / 'results.json').write_text(json.dumps(result, indent=2) + '\n')
    print(json.dumps(result, indent=2))
    return int(result['status'] != 'PASS')


if __name__ == '__main__':
    raise SystemExit(main())
