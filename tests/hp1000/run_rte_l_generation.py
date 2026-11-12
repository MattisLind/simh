"""Generate a genuine memory-based RTE-L validation SYSTEM and boot a 7902 copy.

Runs HP READR, LOADR and RTLGN under the supplied RTE-IVB host. This stops OS
validation after loading SYSTEM at the kernel entry; run_rte_l_boot.py continues.
It does not claim an installed disk-based FMGR system or a diagnostic pass.
"""
import argparse
import hashlib
import json
import re
import struct
from pathlib import Path
from firmware import read_pair
from rte_archive import saver_tape
from rte_disk import append_files
from rte_records import encode_text, decode_text
from run_baseline import execute


def host_files(path, requested):
    """Read complete, contiguous files from the supplied host's SC cartridge."""
    raw = path.read_bytes()
    data = bytearray(raw)
    data[::2], data[1::2] = raw[1::2], raw[::2]
    track_bytes = 48 * 256
    headers = []
    for offset in range(0, len(data), track_bytes):
        name = bytes([data[offset] & 127]) + data[offset + 1:offset + 6]
        if name == b'SCRTCH':
            h = struct.unpack('>16H', data[offset:offset + 32])
            if h[3] == 0x5343 and h[6] == 96 and h[8] == 65535:
                headers.append((offset, h))
    if len(headers) != 1:
        raise ValueError('no unique supported single-track SC directory')
    offset, header = headers[0]
    base = offset - header[7] * track_bytes
    result = {}
    for pos in range(offset + 32, offset + track_bytes, 32):
        record = data[pos:pos + 32]
        name = record[:6].decode('ascii', errors='replace').rstrip()
        if name not in requested:
            continue
        words = struct.unpack('>16H', record)
        start = base + words[4] * track_bytes + words[5] * 128
        payload = bytes(data[start:start + words[6] * 128])
        if name in result or len(payload) != words[6] * 128:
            raise ValueError('duplicate or truncated host file')
        result[name] = (words[3], payload)
    if set(result) != set(requested):
        raise ValueError('generator output file absent')
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--simulator', type=Path, default=Path('BIN/hp2100'))
    parser.add_argument('--output', type=Path, default=Path('build/hp1000/rte-l-generated'))
    parser.add_argument('--commands', type=Path, default=Path('tests/hp1000/config/rte-l-7902.gen'))
    args = parser.parse_args()
    out = args.output
    out.mkdir(parents=True, exist_ok=True)
    kit = Path('hp1000-references/software/operating-systems/RTE-IVB')
    original_host = kit / 'RTE-IVB-SYSTEM.U0.7920H.disc'
    master = Path('hp1000-references/software/operating-systems/92070-13401.hpi')
    sources = {str(p): hashlib.sha256(p.read_bytes()).hexdigest() for p in [original_host, master]}
    raw = original_host.read_bytes()
    if len(raw) != 48 * 5 * 823 * 256:
        raise ValueError('unsupported supplied host geometry')
    swapped = bytearray(raw)
    swapped[::2], swapped[1::2] = raw[1::2], raw[::2]
    host = out / 'host.disc'
    host.write_bytes(swapped)
    answers = args.commands.read_text()
    (out / 'GENCMD.txt').write_text(answers)
    tape = out / 'input.tap'
    manifest = saver_tape(master, tape, [('GENCMD', 3, encode_text(answers))])
    (out / 'import-manifest.json').write_text(json.dumps(manifest, indent=2) + '\n')
    config, after = (kit / 'RTE-IVB.sim').read_text().rsplit('boot DA0', 1)
    if after.strip():
        raise ValueError('unexpected packaged host configuration')
    config = config.replace('set CPU IDLE', 'set CPU NOIDLE').replace(
        'attach DA0 RTE-IVB-SYSTEM.U0.7920H.disc', f'attach DA0 {host.resolve()}')
    commands = ['set on', 'on error exit 1', config,
                f'attach -r MSC0 {tape.resolve()}', 'runlimit 10000000',
                'on error ignore', 'boot DA0', 'norunlimit', 'on error exit 1',
                'send after=10000,delay=10000,"\\r"']

    def step(count):
        commands.extend(['on error ignore', f'step {count}', 'on error exit 1'])

    def send(text, count):
        commands.append(f'send "{text}\\r"')
        step(count)

    step(1000000)
    send('RU,FMGR', 3000000)
    send('RU,READR', 3000000)
    send('OC,SC', 2000000)
    send('AL', 1000000)
    send('EN', 70000000)
    send('AB', 2000000)
    send('RU,LOADR', 3000000)
    send('SZ,24', 2000000)  # default 11 pages leaves <1KW free and causes OV FIX
    send('LI,$LDRLB::SC', 2000000)
    send('LI,$MXLB::SC', 2000000)
    send('RE,\\045RTLGN::SC', 200000000)
    send('EN', 30000000)
    send('RU,RTLGN,GENCMD::SC,SYSTEM::SC,SNAP::SC,SYLIST::SC', 80000000)
    commands.extend(['echo HP1000_CHECK_PASS', 'exit'])
    script = out / 'generate.ini'
    script.write_text('\n'.join(commands) + '\n')
    generation = execute(args.simulator.resolve(), script, script.with_suffix('.log'), 240)
    transcript = script.with_suffix('.log').read_text(errors='replace')
    if generation['status'] != 'PASS' or not re.search(r'\*\s+0 ERRORS \*', transcript):
        raise RuntimeError('RTLGN did not complete cleanly; inspect generate.log')
    files = host_files(host, ['SYSTEM', 'SNAP', 'SYLIST'])
    for name, (kind, payload) in files.items():
        (out / (name + '.bin')).write_bytes(payload)
    listing = decode_text(files['SYLIST'][1])
    (out / 'SYLIST.txt').write_text(listing)
    if not re.search(r'\*\s+0 ERRORS \*', listing) or 'GEN AB' in listing:
        raise RuntimeError('SYLIST does not confirm clean completion')
    system = files['SYSTEM'][1]
    if files['SYSTEM'][0] != 1 or len(system) != 65536:
        raise ValueError('unexpected generated SYSTEM format')
    words = struct.unpack('>32768H', system)
    if words[1:3] != (2, 0o124003) or not 0 < words[3] <= words[0] < 0o76500:
        raise ValueError('unexpected generated load/start header')
    image = out / 'rte-l-7902.hpi'
    directory = append_files(master, image, [(name, *files[name]) for name in ['SYSTEM', 'SNAP']])
    (out / 'target-directory.json').write_text(json.dumps(directory, indent=2) + '\n')
    root = Path('hp1000-references/software/diagnostics/archives/type-4')
    rom, _ = read_pair(root / '12001-16001_Rev-2140.src', root / '12001-16002_Rev-2150.src')
    rom_path = out / 'rom.bin'
    rom_path.write_bytes(b''.join(w.to_bytes(2, 'big') for w in rom))
    entry = words[3]
    boot = ['set on', 'on error exit 1', 'set cpu 1000-L', 'set ASI enabled',
            'set HPI enabled', f'set cpu LROM={rom_path.resolve()}',
            f'attach -r HPI0 {image.resolve()}', f'attach ASI {(out / "boot-console.txt").resolve()}',
            'deposit S 400', 'reset -p', 'on error ignore', 'step 50000000',
            'on error exit 1', 'assert LSTATUS=207', f'break {entry:o}',
            'send "\\045BDC27\\r"', 'on error ignore', 'step 30000000',
            'on error exit 1', f'assert P={entry:o}', 'assert LROMEN=0']
    boot.extend(f'assert {i:o}={words[i]:o}' for i in range(2, 0o76000))
    boot.extend(['ex HPI TRANSFERS', 'echo ORIGINAL_SYSTEM_LOADED',
                 'echo HP1000_CHECK_PASS', 'exit'])
    boot_script = out / 'boot.ini'
    boot_script.write_text('\n'.join(boot) + '\n')
    boot_result = execute(args.simulator.resolve(), boot_script, boot_script.with_suffix('.log'), 120)
    unchanged = all(hashlib.sha256(Path(p).read_bytes()).hexdigest() == digest for p, digest in sources.items())
    result = dict(generation=generation, boot=boot_result, generation_complete=True,
                  original_sources_unchanged=unchanged, sources=sources,
                  SYSTEM_sha256=hashlib.sha256(system).hexdigest(), kernel_entry=f'{entry:05o}',
                  SYSTEM_loaded=boot_result['status'] == 'PASS', memory_words_compared=0o76000 - 2,
                  configuration='RTE-L memory-based COMND, 32KW, ASI SC20, HPI SC27, 7902 LU2/3, four IDs',
                  class_entries=int(re.search(r'^CL,(\d+)$', answers, re.M)[1]),
                  sam_words=int(re.search(r'^SA,(\d+)$', answers, re.M)[1]),
                  disk_based_FMGR_installed=False, diagnostics='NOT_RUN_BY_THIS_SCRIPT',
                  next='run_rte_l_boot.py verifies HP2645 handshake, COMND prompt and TM')
    (out / 'results.json').write_text(json.dumps(result, indent=2) + '\n')
    print(json.dumps(result, indent=2))
    return int(not unchanged or boot_result['status'] != 'PASS')


if __name__ == '__main__':
    raise SystemExit(main())
