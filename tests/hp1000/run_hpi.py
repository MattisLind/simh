"""Bounded 12009A tests, authentic RTE-L BOOTX and diagnostic-disc startup.

A BOOTX 'SYSTEM not found' halt is a verified checkpoint, never an RTE pass.
All reference media are attached read-only; no guest firmware is patched.
"""
import argparse
import hashlib
import json
from pathlib import Path
from firmware import read_pair
from rte_disk import inspect
from run_baseline import execute


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--simulator', type=Path, default=Path('BIN/hp2100'))
    parser.add_argument('--output', type=Path, default=Path('build/hp1000/12009a/tests'))
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    results = []

    def run(name, commands):
        script = args.output / (name + '.ini')
        script.write_text('set on\non error exit 1\n' + '\n'.join(commands)
                          + '\necho HP1000_CHECK_PASS\nexit\n')
        result = execute(args.simulator.resolve(), script, script.with_suffix('.log'), 120)
        result['test'] = name
        results.append(result)
        return result

    commands = ['set cpu 1000-L', 'set HPI enabled', 'reset -p']

    def instruction(text, a=None, expected=None):
        if a is not None:
            commands.append(f'deposit A {a:o}')
        commands.extend([f'deposit 100 {text}', 'deposit P 100', 'on error ignore',
                         'step', 'on error exit 1'])
        if expected:
            commands.extend(f'assert {reg}={value:o}' for reg, value in expected.items())

    def wait(steps=80):
        commands.extend(['deposit 1000 JMP 1000', 'deposit P 1000',
                         'on error ignore', f'step {steps}', 'on error exit 1'])

    instruction('OTA 2', 1)
    instruction('LIA 27', 0, {'A': 0o4027})
    instruction('LIA 2', 0, {'A': 0o4027})
    instruction('LIA 2', 0o1234, {'A': 0o1234})
    instruction('OTA 2', 0)
    instruction('OTA 2,C', 0o27)
    instruction('OTA 0', 0o177776)
    instruction('LIA 0', 0, {'A': 0o177777})
    instruction('OTA 0', 0)
    instruction('OTA 31', 0o125252)
    instruction('LIA 31', expected={'A': 0o125252})
    instruction('OTA 31', 0o177777)
    instruction('LIA 31', expected={'A': 0})
    for value in [0o70200, 0o60063, 0o60042]:
        instruction('OTA 30', value)
        instruction('STC 30,C')
        wait()
    instruction('OTA 30', 0o170000)
    instruction('STC 30,C')
    instruction('LIA 30', expected={'A': 0o170200})
    instruction('STC 30,C')
    instruction('LIA 30', expected={'A': 0o170200})
    instruction('OTA 30', 0o110000)
    instruction('STC 30,C')
    instruction('LIA 30', expected={'A': 0o110030})
    run('card-registers', commands)

    # Diagnose-2 status carries GR in bits 5..0, not the responding card SC.
    # With GR=27, ASI responds first with low bits 27; that must not cause
    # the CPU to reinterpret the already converted ASI status as HPI status.
    commands = ['set cpu 1000-L', 'set ASI enabled', 'set HPI enabled', 'reset -p']
    instruction('OTA 2', 2)
    instruction('OTA 2', 0o27)
    instruction('LIA 2', expected={'A': 0o14027})
    instruction('LIA 2', expected={'A': 0o4227})
    instruction('LIA 20', expected={'A': 0o14027})
    instruction('LIA 27', expected={'A': 0o4227})
    instruction('CLF 2')
    instruction('LIA 20', expected={'A': 0o14127})
    instruction('LIA 27', expected={'A': 0o4327})
    instruction('OTA 2', 0o20)
    instruction('STF 22')
    instruction('OTA 2', 0o27)
    instruction('LIA 27', expected={'A': 0o327})
    instruction('OTA 0', 0o20)
    instruction('LIA 27', expected={'A': 0o4327})
    run('two-card-diagnose-2-response-routing', commands)

    commands = ['set cpu 1000-L', 'set HPI enabled', 'reset -p']
    instruction('OTA 2,C', 0o27)
    instruction('STC 30')
    instruction('STF 30')
    instruction('CLC 4')
    instruction('STF 0')
    commands += ['deposit 27 JSB 400', 'deposit 200 100201', 'deposit 201 100202',
                 'deposit 202 100203', 'deposit 203 300', 'deposit 400 0']
    instruction('JMP 200,I', expected={'P': 0o300})
    instruction('STC 4')
    instruction('JMP 200,I', expected={'P': 0o100, 'INTEN': 1})
    commands += ['on error ignore', 'step', 'on error exit 1', 'assert P=401',
                 'assert 400=100', 'assert CIR=27', 'assert LGR=27', 'assert LGRDIS=0']
    run('card-interrupt-in-indirect-chain', commands)

    # Original 24397-18009 lines 54..68 exercise the packed card data path.
    # This does not bypass the HP-IB chip for ordinary READ-selected input.
    commands = ['set cpu 1000-L', 'set HPI enabled', 'reset -p']
    instruction('OTA 2,C', 0o27)
    instruction('OTA 30', 0o60003)
    instruction('STC 30,C')
    for address, value in enumerate([0o175000, 0o2000, 0o600, 0o177776,
                                     0o61200, 0o2000, 0o601, 0o177776], 0o500):
        commands.append(f'deposit {address:o} {value:o}')
    commands += ['deposit 600 125252', 'deposit 601 0']
    instruction('OTA 20', 0o500)
    instruction('STC 20,C')
    wait(2000)
    commands += ['assert 601=125252', 'assert 503=0', 'assert HPI DMAEN=0',
                 'assert HPI FLAGS=1']
    instruction('LIA 20', expected={'A': 0o100510})
    run('packed-DMA-chain-and-residue', commands)

    # Use the existing DA Amigo hard-disc endpoint through the new frontend.
    hard = args.output / '7906-test.bin'
    with hard.open('wb') as stream:
        stream.truncate(48 * 4 * 411 * 128 * 2)
    commands = ['set cpu 1000-L', 'set HPI enabled', 'set HPI HARDDISK',
                'set DA enabled', f'attach -r DA0 {hard.resolve()}', 'reset -p']
    instruction('OTA 2,C', 0o27)
    for value in [0o70200, 0o60063, 0o60042, 0o537, 0o477, 0o476,
                  0o537, 0o540, 0o1002]:
        instruction('OTA 30', value)
        instruction('STC 30,C')
        wait(200000)
    instruction('OTA 30', 0o100000)
    instruction('STC 30,C')
    instruction('LIA 30', expected={'A': 0o100000})
    instruction('STC 30,C')
    instruction('LIA 30', expected={'A': 0o101403})
    run('existing-DA-identify', commands)

    # Exercise a real write on synthetic scratch media, then compare the entire
    # image on the host so an incorrect seek/extent cannot pass unnoticed.
    scratch = args.output / 'scratch.hpi'
    original = bytes(77 * 2 * 30 * 256)
    scratch.write_bytes(original)
    payload = bytes(range(256))
    commands = ['set cpu 1000-L', 'set HPI enabled',
                f'attach HPI0 {scratch.resolve()}', 'reset -p']
    instruction('OTA 2,C', 0o27)

    def phi_output(value):
        instruction('OTA 30', value)
        instruction('STC 30,C')
        wait()

    for value in [0o70200, 0o60063, 0o60042,
                  0o537, 0o477, 0o536, 0o440, 0o550, 2, 0, 0, 0, 1, 0o1002,
                  0o537, 0o477, 0o536, 0o440, 0o550, 8, 0o1000,
                  0o537, 0o477, 0o536, 0o440, 0o540]:
        phi_output(value)
    for i in range(128):
        commands.append(f'deposit {0o600+i:o} {int.from_bytes(payload[i*2:i*2+2], "big"):o}')
    instruction('OTA 21', 0o60000)
    instruction('OTA 22', 0o600)
    instruction('OTA 23', 0o177400)
    instruction('OTA 31', 0o3000)
    instruction('STC 21,C')
    wait(20000)
    commands += ['assert HPI DMAEN=0', 'assert HPI FLAGS=2']
    result = run('floppy-byte-DMA-write', commands)
    expected = bytearray(original)
    expected[(30+2)*256:(30+3)*256] = payload
    if scratch.read_bytes() != expected:
        result['status'] = 'FAIL'

    # 07902-90030 A-29..30, A-38..39: a buffered read preloads exactly
    # one sector. A short buffered write commits at EOI and retains the
    # remainder of that controller buffer, even after an abbreviated read.
    buffered = args.output / 'buffered.hpi'
    original = bytes((i * 17 + 3) & 255 for i in range(77 * 2 * 30 * 256))
    buffered.write_bytes(original)
    commands = ['set cpu 1000-L', 'set HPI enabled',
                f'attach HPI0 {buffered.resolve()}', 'reset -p']
    instruction('OTA 2,C', 0o27)
    for value in [0o70200, 0o60063, 0o60042,
                  0o537, 0o477, 0o536, 0o440, 0o550, 2, 0, 0, 0, 0, 0o1002,
                  0o537, 0o477, 0o536, 0o440, 0o552, 5, 0o1000]:
        phi_output(value)
    commands += ['assert HPI FDSECTOR[0]=3', 'assert HPI FDREPLYCOUNT=256']
    for value in [0o537, 0o477, 0o476, 0o500, 0o540, 0o1004, 0o60040]:
        phi_output(value)
    for index, value in enumerate(original[512:516]):
        phi_output(0o100000)
        instruction('LIA 30', expected={'A': 0o100000 | value
                                      | (0o1000 if index == 3 else 0)})
    commands += ['assert HPI FDSECTOR[0]=3', 'assert HPI FDREPLYPOS=4']
    for value in [0o537, 0o477, 0o536, 0o440, 0o551, 8, 0o1000,
                  0o537, 0o477, 0o536, 0o440, 0o540, 0o252, 0o1273]:
        phi_output(value)
    commands += ['assert HPI FDSECTOR[0]=4', 'assert HPI FDWRITE=0',
                 'assert HPI FDDSJ=0']
    result = run('floppy-buffered-read-and-short-write', commands)
    expected = bytearray(original)
    expected[768:1024] = bytes([0xaa, 0xbb]) + original[514:768]
    if buffered.read_bytes() != expected:
        result['status'] = 'FAIL'

    commands = ['set cpu 1000-L', 'set HPI enabled', 'reset -p']
    instruction('OTA 2,C', 0o27)
    for value in (0o70140, 0o70040, 0o60042, 0o31114, 0o21777, 0o537, 0o1010):
        phi_output(value)
    commands += ['assert HPI TALK=1', 'assert HPI LISTEN=1',
                 'assert HPI INCOUNT=2', 'assert HPI BUSCTL=0',
                 'deposit 300 51200', 'deposit 301 101000',
                 'deposit 302 400', 'deposit 303 177774']
    instruction('OTA 30', 0o60040)
    instruction('STC 30,C')
    instruction('OTA 20', 0o300)
    instruction('STC 20,C')
    wait(200)
    commands += ['assert 400=100337', 'assert 401=101410',
                 'assert 303=177776', 'assert HPI DMAEN=0', 'assert HPI INCOUNT=0']
    instruction('LIA 32', expected={'A': 0o24036})
    instruction('OTA 30', 0o120000)
    instruction('STC 30,C')
    instruction('LIA 32', expected={'A': 0o4036})
    run('offline-PHI-wrap-parity-word-DMA-and-EOR-residue', commands)

    commands = ['set cpu 1000-L', 'set HPI enabled', 'reset -p']
    instruction('OTA 2,C', 0o27)
    for value in (0o70140, 0o60042, 0o31100, 0o21777):
        phi_output(value)
    for i in range(18):
        commands.append(f'deposit {0o400+i:o} {i:o}')
    instruction('OTA 31', 0)
    instruction('OTA 21', 0o40000)
    instruction('OTA 22', 0o400)
    instruction('OTA 23', 0o177756)
    instruction('STC 21,C')
    wait(1000)
    commands += ['assert HPI DMAEN=1', 'assert HPI INCOUNT=8', 'assert HPI OUTCOUNT=8']
    instruction('LIA 23', expected={'A': 0o177777})
    instruction('CLC 23,C')
    phi_output(0o120000)
    instruction('LIA 30', expected={'A': 0o120000})
    # The unaccepted word was prefetched, not a PHI processor-handshake abort.
    instruction('OTA 31', 0o100000)
    instruction('OTA 21', 0o40200)
    instruction('OTA 22', 0o500)
    instruction('OTA 23', 0o177742)
    instruction('STC 21,C')
    wait(1000)
    instruction('LIA 23', expected={'A': 0o177762})
    commands += ['assert HPI INCOUNT=0', 'assert HPI OUTCOUNT=0']
    for i in range(16):
        commands.append(f'assert {0o500+i:o}={0o100000+i:o}')
    run('offline-FIFO-backpressure-prefetch-and-drain', commands)

    commands = ['set cpu 1000-L', 'set HPI enabled', 'reset -p']
    instruction('OTA 2,C', 0o27)
    phi_output(0o100000)  # Empty programmed FIFO read latches handshake abort.
    phi_output(0o30777)
    commands += ['deposit 300 51200', 'deposit 301 104010',
                 'deposit 302 600', 'deposit 303 177777', 'deposit 600 12345']
    instruction('OTA 20', 0o300)
    instruction('STC 20,C')
    wait(1000)
    commands += ['assert 600=12345', 'assert HPI DMAEN=1']
    instruction('CLC 23,C')
    phi_output(0o31100)
    instruction('OTA 20', 0o300)
    instruction('STC 20,C')
    wait(200)
    commands += ['assert HPI DMAEN=0', 'assert 600=100000']
    run('DMA-delay-requires-enabled-interrupt-condition', commands)

    commands = ['set cpu 1000-L', 'set HPI enabled', 'reset -p']
    instruction('OTA 2,C', 0o27)
    for value in (0o60062, 0o60052, 0o31040, 0o40377, 0o50000,
                  0o536, 0o476, 0o405):
        phi_output(value)
    for line in (0, 1, 7):
        phi_output(0o550 + line)
        phi_output(0o120000)
        instruction('LIA 30', expected={'A': 0o121040})
        phi_output(0o100000)
        instruction('LIA 30', expected={'A': 0o100000 | (1 << line)})
    for value in (0o537, 0o477, 0o536, 0o476, 0o574):
        phi_output(value)
    phi_output(0o100000)
    instruction('LIA 30', expected={'A': 0o100434})
    commands += ['deposit 400 10000']
    instruction('LIA 32')
    instruction('AND 400', expected={'A': 0o10000})
    instruction('OTA 32', 0)
    instruction('LIA 32')
    instruction('AND 400', expected={'A': 0})
    phi_output(0o110000)
    # The MSA's DO/D1 tag remains available through the high-order access bits.
    instruction('LIA 30', expected={'A': 0o110136})
    run('offline-addressing-parallel-poll-and-secondary-latch', commands)

    commands = ['set cpu 1000-L', 'set HPI enabled', 'reset -p']
    instruction('OTA 2,C', 0o27)
    phi_output(0o70140)
    for value in range(8):
        phi_output(value)
    commands += ['deposit 300 71000', 'deposit 301 2002', 'deposit 302 400',
                 'deposit 303 177776', 'deposit 400 11064']
    instruction('OTA 20', 0o300)
    instruction('STC 20,C')
    wait(500)
    instruction('LIA 23', expected={'A': 0})
    commands += ['assert HPI DMAEN=1', 'assert HPI INCOUNT=8', 'assert HPI OUTCOUNT=2']
    instruction('SFC 20', expected={'P': 0o102})
    run('PPOLL-N-plus-one-handshake-defers-DMA-completion', commands)

    # PHI register 6 selects the FIFO generating DMARQ independently of
    # the IOP's IN bit (3-49). The original ID.37 CLRIN uses outbound
    # selection to clock an eight-byte inbound drain even when it is empty.
    commands = ['set cpu 1000-L', 'set HPI enabled', 'reset -p']
    instruction('OTA 2,C', 0o27)
    phi_output(0o60002)
    commands += ['deposit 300 61200', 'deposit 301 102000',
                 'deposit 302 400', 'deposit 303 177770']
    instruction('OTA 20', 0o300)
    instruction('STC 20,C')
    wait(2000)
    commands += ['assert HPI DMAEN=0', 'assert HPI REGS[19]=0',
                 'assert HPI REGS[18]=404', 'assert HPI INCOUNT=0']
    run('PHI-DMARQ-FIFO-selector-independent-of-IOP-direction', commands)

    root = Path('hp1000-references/software/diagnostics/archives/type-4')
    words, _ = read_pair(root / '12001-16001_Rev-2140.src', root / '12001-16002_Rev-2150.src')
    rom = args.output / 'processor-rom.bin'
    rom.write_bytes(b''.join(w.to_bytes(2, 'big') for w in words))
    rte = Path('hp1000-references/software/operating-systems/92070-13401.hpi')
    diagnostic = Path('hp1000-references/software/diagnostics/archives/24397A.hpi')

    def startup(image, console):
        return ['set cpu 1000-L', 'set ASI enabled', 'set HPI enabled',
                f'set cpu LROM={rom.resolve()}', f'attach -r HPI0 {image.resolve()}',
                f'attach ASI {console.resolve()}', 'deposit S 400', 'reset -p',
                'on error ignore', 'step 50000000', 'on error exit 1',
                'assert LSTATUS=207', 'assert LPSAVE=77777', 'assert 77772=2']

    console = args.output / 'rte-l-console.txt'
    commands = startup(rte, console)
    commands += ['break 2', 'send "\\045BDC27\\r"', 'on error ignore',
                 'step 30000000', 'on error exit 1', 'assert P=2',
                 'assert LROMEN=0', 'assert HPI TRANSFERS=65408']
    data = rte.read_bytes()
    # Check the low 31KW against the image before BOOTX executes. The upper
    # ROM execution page contains the loader's live return cells/workspace.
    commands += [f'assert {address:o}={int.from_bytes(data[address*2:address*2+2], "big"):o}'
                 for address in range(2, 0o76000)]
    commands += ['nobreak 2', 'break 204', 'on error ignore', 'step 10000000',
                 'on error exit 1', 'assert P=204', 'assert LROMEN=0',
                 'assert 204=102002', 'nobreak 204', 'on error ignore', 'step 1',
                 'on error exit 1', 'assert LPSAVE=205', 'assert LROMEN=1']
    result = run('RTE-L-BOOTX-missing-SYSTEM', commands)
    directory = inspect(rte)
    (args.output / 'rte-l-directory.json').write_text(json.dumps(directory, indent=2) + '\n')
    if directory['has_SYSTEM']:
        result['status'] = 'FAIL'
    result.update(RTE_L_running=False, stop='BOOTX HLT 2: SYSTEM absent',
                  image_sha256=directory['sha256'])

    console = args.output / 'diagnostic-console.txt'
    commands = startup(diagnostic, console)
    commands += ['send "\\045BDC27HPIB\\r"', 'on error ignore',
                 'step 30000000', 'on error exit 1', 'assert LROMEN=0']
    result = run('original-12009-diagnostic-startup', commands)
    transcript = console.read_bytes() if console.exists() else b''
    if b'12009A HP-IB INTERFACE DIAGNOSTIC' not in transcript or b'READY' not in transcript:
        result['status'] = 'FAIL'
    result.update(diagnostic_full_pass=False, console=str(console),
                  image_sha256=hashlib.sha256(diagnostic.read_bytes()).hexdigest())
    (args.output / 'diagnostic-directory.json').write_text(json.dumps(inspect(diagnostic), indent=2) + '\n')
    report = dict(results=results, RTE_L_running=False,
                  remaining='Generate a SYSTEM image or obtain a generated RTE-L system; complete card diagnostic coverage')
    (args.output / 'results.json').write_text(json.dumps(report, indent=2) + '\n')
    for result in results:
        print(result['status'], result['test'])
    return int(any(r['status'] != 'PASS' for r in results))


if __name__ == '__main__':
    raise SystemExit(main())
