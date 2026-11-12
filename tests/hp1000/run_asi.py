"""HP 12005A PIO/shared-chip tests and original ROM VCP startup/interaction.

Requires privately supplied original PROM files. No firmware or diagnostic is
patched, and console replies are produced by HP firmware, not a host parser.
"""
import argparse
import hashlib
import json
from pathlib import Path
from firmware import read_pair
from run_baseline import execute


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--simulator', type=Path, default=Path('BIN/hp2100'))
    parser.add_argument('--output', type=Path, default=Path('build/hp1000/12005a'))
    parser.add_argument('--root', type=Path, default=Path('hp1000-references/software/diagnostics/archives/type-4'))
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    results = []

    def run(name, commands, timeout=30):
        script = args.output / (name + '.ini')
        script.write_text('set on\non error exit 1\n' + '\n'.join(commands)
                          + '\necho HP1000_CHECK_PASS\nexit\n')
        result = execute(args.simulator.resolve(), script, script.with_suffix('.log'), timeout)
        result['test'] = name
        results.append(result)
        return result

    commands = ['set cpu 1000-L', 'set ASI enabled', 'reset -p']
    cases = []

    def instruction(text, a=None, b=None, expected=None):
        if a is not None: commands.append(f'deposit A {a:o}')
        if b is not None: commands.append(f'deposit B {b:o}')
        commands.extend([f'deposit 100 {text}', 'deposit P 100', 'on error ignore',
                         'step', 'on error exit 1'])
        if expected:
            commands.extend(f'assert {reg}={value:o}' for reg, value in expected.items())

    def passed(name):
        cases.append(name)
        commands.append('echo ASI_CASE_PASS_' + name)

    def wait():
        commands.extend(['deposit P 1000', 'on error ignore', 'step 1000', 'on error exit 1'])

    instruction('OTA 2', 1)
    instruction('LIA 20', 0, expected={'A': 0o20})
    instruction('LIA 2', 0, expected={'A': 0o20})
    instruction('LIA 2', 0o12345, expected={'A': 0o12345})
    passed('identity_priority_and_direct')
    instruction('OTA 2', 0)
    instruction('OTA 2,C', 0o20)
    instruction('LIA 2', 0, expected={'A': 0o20})
    passed('selected_global')
    instruction('OTA 20', 0o52525)
    instruction('LIA 20', expected={'A': 0o152525})
    instruction('OTA 21', 0)
    instruction('OTA 22', 0o125252)
    instruction('LIA 22', expected={'A': 0o125252})
    instruction('OTA 21', 0o200)
    instruction('LIA 22', expected={'A': 0o25252})
    instruction('MIA 22', 0o40000, expected={'A': 0o65252})
    passed('IOP_configuration_and_DMA_address_readback')
    instruction('OTA 0', 0o177776)
    instruction('LIA 0', 0, expected={'A': 0o177777})
    instruction('OTA 0', 0)
    passed('distributed_mask')
    instruction('STF 30')
    instruction('SFS 30,C', expected={'P': 0o102, 'ASI FLAGS': 0})
    passed('flag_test_before_clear')
    instruction('OTA 32', 1)
    instruction('OTA 31', 0o3404)
    instruction('LIA 31', expected={'A': 0o3404})
    instruction('OTA 30', 0o252)
    instruction('STC 30,C')
    wait()
    instruction('SFS 30', expected={'P': 0o102})
    instruction('LIA 30,C', expected={'A': 0o252, 'ASI FLAGS': 0})
    passed('eight_bit_UART_loopback')
    instruction('OTA 32', 0)
    instruction('OTA 31', 0o6412)
    commands += ['deposit ASI RX 101', 'deposit ASI RXREADY 1']
    instruction('STC 30,C')
    wait()
    instruction('LIA 30,C', expected={'A': 0o101})
    passed('receive_and_echo')
    # Exactly the original pretest's self-configuration/diagnose-3 word path.
    commands += ['deposit 500 200', 'deposit 501 600', 'deposit 502 177775']
    instruction('OTA 20', 0o500)
    instruction('OTA 2', 7)
    instruction('STC 20,C')
    instruction('SFS 24', expected={'P': 0o102})
    instruction('LIA 21', expected={'A': 0o200})
    instruction('OTA 2', 3)
    wait()
    commands += ['assert 600=503', 'assert 601=504', 'assert 602=505']
    instruction('LIA 23', expected={'A': 0})
    instruction('SFC 24', expected={'P': 0o102})
    passed('self_configuration_and_diagnose_3')
    instruction('OTA 0', 0o177777)
    instruction('CLC 0,C', expected={'ASI SRQMASK': 0, 'ASI FLAGS': 0, 'ASI MASK': 0, 'LIMASK': 0})
    passed('CRS_stops_IO')
    # Original KERN DMP03-style AUTO/RES/CONT chain, with no external SRQ.
    instruction('OTA 2,C', 0o20)
    instruction('OTA 2', 7)
    for address, value in enumerate([0o114400, 0o600, 0o177777,
                                     0o5400, 0, 0o100601, 0o177777], 0o500):
        commands.append(f'deposit {address:o} {value:o}')
    commands += ['deposit 600 12345', 'deposit 601 54321']
    instruction('OTA 20', 0o500)
    instruction('STC 20,C')
    instruction('LIA 20', expected={'A': 0o100507})
    instruction('LIA 22', expected={'A': 0o100602})
    instruction('LIA 23', expected={'A': 0})
    commands += ['assert 502=0', 'assert 506=177777', 'assert ASI DMAEN=0']
    instruction('SFS 20', expected={'P': 0o102})
    passed('AUTO_residue_and_quadruplet_chain_without_external_SRQ')
    instruction('CLC 0,C')
    # Bad parity on a configuration fetch belongs to the IOP, not CPU SC5.
    instruction('OTA 2,C', 0o20)
    instruction('OTA 2', 7)
    commands += ['deposit 501 600', 'deposit 502 177777']
    instruction('STF 5')
    instruction('STA 500', 0o200)
    instruction('CLF 5')
    instruction('STC 5')
    instruction('OTA 20', 0o500)
    instruction('STC 20,C')
    instruction('LIA 20', expected={'A': 0o100501, 'ASI FLAGS': 4,
                                   'ASI DMAEN': 0, 'LPARIRQ': 0, 'LPFAULT': 0})
    passed('DMA_configuration_parity_is_reported_by_the_IOP')
    instruction('CLC 5')
    instruction('STA 500', 0o200)
    instruction('CLC 0,C')
    # An actual card flag interrupts a deferred indirect jump, not a timer flag.
    instruction('OTA 2,C', 0o20)
    instruction('STC 30')
    instruction('STF 30')
    instruction('CLC 4')
    instruction('STF 0')
    commands += ['deposit 20 JSB 400', 'deposit 200 100201', 'deposit 201 100202',
                 'deposit 202 100203', 'deposit 203 300', 'deposit 400 0']
    instruction('JMP 200,I', expected={'P': 0o300})
    instruction('STC 4')
    instruction('JMP 200,I', expected={'P': 0o100, 'INTEN': 1})
    commands += ['on error ignore', 'step', 'on error exit 1', 'assert P=401',
                 'assert 400=100', 'assert CIR=20', 'assert LGR=20', 'assert LGRDIS=0']
    passed('card_interrupt_in_indirect_chain')
    run('programmed-io', commands)

    commands = ['set cpu 1000-L', 'set ASI enabled', 'set ASI1 enabled',
                'set ASI1 LOOPBACK', 'set HPI enabled', 'reset -p']
    instruction('OTA 2', 1)
    for identity in (0o20, 0o4027, 0o21):
        instruction('LIA 2', 0, expected={'A': identity})
    instruction('LIA 2', 0o12345, expected={'A': 0o12345})
    instruction('LIA 21', 0, expected={'A': 0o21})
    instruction('OTA 2', 0)
    instruction('OTA 2,C', 0o21)
    instruction('OTA 31', 0o3404)
    instruction('OTA 30', 0o252)
    instruction('STC 30,C')
    wait()
    instruction('LIA 30,C', expected={'A': 0o252, 'ASI FLAGS': 0, 'ASI1 FLAGS': 0})
    instruction('CLC 0,C')
    instruction('OTA 2,C', 0o21)
    instruction('STC 30')
    instruction('STF 30')
    instruction('CLC 4')
    instruction('STF 0')
    commands += ['deposit 21 JSB 400', 'deposit 200 100201', 'deposit 201 100202',
                 'deposit 202 100203', 'deposit 203 300', 'deposit 400 0']
    instruction('JMP 200,I', expected={'P': 0o300})
    instruction('STC 4')
    instruction('JMP 200,I', expected={'P': 0o100, 'INTEN': 1})
    commands += ['on error ignore', 'step', 'on error exit 1', 'assert P=401',
                 'assert 400=100', 'assert CIR=21', 'assert LGR=21', 'assert LGRDIS=0']
    run('second-ASI-enumeration-loopback-and-interrupt', commands)

    commands = ['set cpu 1000-L', 'set ASI1 enabled', 'set ASI1 LOOPBACK', 'reset -p']
    instruction('OTA 2,C', 0o21)
    instruction('OTA 32', 1)
    commands += ['deposit 300 165400', 'deposit 301 3574', 'deposit 302 400',
                 'deposit 303 177776', 'deposit 304 61600', 'deposit 305 3574',
                 'deposit 306 401', 'deposit 307 177776', 'deposit 400 125252',
                 'deposit 401 0']
    instruction('OTA 20', 0o300)
    instruction('STC 20,C')
    wait()
    commands += ['assert 401=125252', 'assert ASI1 DMAEN=0']
    instruction('SFS 20', expected={'P': 0o102})
    instruction('SFS 21', expected={'P': 0o102})
    instruction('CLC 23,C')
    instruction('OTA 32', 1)
    commands += ['deposit 300 71600', 'deposit 301 43574', 'deposit 302 401',
                 'deposit 303 177776', 'deposit 401 0']
    instruction('OTA 20', 0o300)
    instruction('OTA 30,C', 0o6400)
    instruction('STC 20,C')
    wait()
    commands += ['assert 303=177777', 'assert 401=6400', 'assert ASI1 DMAEN=0']
    run('UART-packed-DMA-direction-change-and-special-termination', commands)

    commands = ['set cpu 1000-L', 'set ASI1 enabled', 'set ASI1 HOOD', 'reset -p']
    instruction('OTA 2,C', 0o21)
    instruction('OTA 32', 0)
    instruction('OTA 31', 4)
    instruction('LIA 32', expected={'A': 0o102316})
    instruction('OTA 31', 7)
    instruction('LIA 32', expected={'A': 0o103376})
    # The hood drives EXTCLK at 1MHz (16 times a 62500-baud serial clock).
    # ECHOM->DRST holds the baud generator reset during the ECHO pulse.
    instruction('OTA 31', 0o5004)
    instruction('OTA 30', 0o125)
    instruction('STC 30,C')
    wait()
    commands += ['assert ASI1 TXWAIT=1', 'assert ASI1 RXREADY=0']
    instruction('OTA 31', 0o1004)
    commands += ['deposit P 1000', 'on error ignore', 'step 80', 'on error exit 1',
                 'assert ASI1 TXWAIT=0', 'assert ASI1 RXREADY=1']
    instruction('LIA 30,C', expected={'A': 0o125})
    instruction('OTA 32', 0)
    instruction('OTA 31', 0o23014)
    instruction('OTA 30', 0o176)
    instruction('STC 30,C')
    instruction('OTA 31', 0o22010)
    wait()
    instruction('OTA 31', 0o22014)
    commands += ['deposit P 1000', 'on error ignore', 'step 100000', 'on error exit 1',
                 'deposit 400 20000']
    instruction('LIA 32')
    instruction('AND 400', expected={'A': 0o20000})
    run('documented-hood-clock-reset-modem-and-parity-error', commands)

    commands = ['set cpu 1000-L', 'set ASI enabled', 'reset -p']
    instruction('OTA 2,C', 0o20)
    commands += ['deposit 300 71600', 'deposit 301 2000', 'deposit 302 400',
                 'deposit 303 177777', 'deposit 400 0']
    instruction('OTA 20', 0o300)
    instruction('STC 20,C')
    commands += ['send "\\006"', 'deposit 1000 JMP 1000', 'deposit P 1000',
                 'on error ignore', 'step 20000', 'on error exit 1',
                 'assert 400=3000', 'assert ASI DMAEN=0', 'assert 303=0']
    run('host-input-wakes-packed-UART-DMA', commands)

    commands = ['set cpu 1000-L', 'set ASI1 enabled', 'set ASI1 LOOPBACK', 'reset -p']
    instruction('OTA 2,C', 0o21)
    instruction('STC 30,C')  # Arm device interrupts while the UART is idle.
    commands += ['deposit 300 75400', 'deposit 301 1004', 'deposit 302 400',
                 'deposit 303 177777', 'deposit 400 52400']
    instruction('OTA 20', 0o300)
    instruction('STC 20,C')
    wait()
    commands += ['assert ASI1 DMAEN=0', 'assert ASI1 IRQ=1']
    instruction('SFS 30', expected={'P': 0o102})
    run('last-UART-TRE-interrupt-survives-DMA-CINT', commands)

    root = args.root
    words, lanes = read_pair(root / '12001-16001_Rev-2140.src', root / '12001-16002_Rev-2150.src')
    image = args.output / 'processor-rom.bin'
    image.write_bytes(b''.join(word.to_bytes(2, 'big') for word in words))
    transcript = args.output / 'vcp-console.txt'
    transcript.write_bytes(b'')
    commands = ['set cpu 1000-L', 'set ASI enabled',
                f'attach ASI {transcript.resolve()}', f'set cpu LROM={image.resolve()}',
                'deposit S 400', 'reset -p', 'assert S=400',
                'on error ignore', 'step 50000000', 'on error exit 1',
                'assert LSTATUS=207', 'assert LROMP=77763', 'assert LPSAVE=77777',
                'assert 77772=1', 'assert ASI CONTROL=6412',
                'echo ORIGINAL_PRETEST_AND_VCP_ENTRY_PASS',
                'send "A000123\\r"', 'on error ignore', 'step 5000000', 'on error exit 1',
                'assert 77772=123', 'echo ORIGINAL_VCP_CHANGE_A_PASS',
                'deposit 100 INA', 'deposit 101 HLT 5',
                'send "P000100\\r"', 'on error ignore', 'step 5000000', 'on error exit 1',
                'assert LPSAVE=100',
                'send "\\045S"', 'on error ignore', 'step 5000000', 'on error exit 1',
                'assert LPSAVE=101', 'assert 77772=124', 'assert LROMEN=1',
                'echo ORIGINAL_VCP_SINGLE_STEP_PASS',
                'send "\\045R"', 'on error ignore', 'step 5000000', 'on error exit 1',
                'assert LPSAVE=102', 'assert 77772=124', 'assert LROMEN=1',
                'echo ORIGINAL_VCP_RUN_HALT_RETURN_PASS']
    result = run('original-vcp', commands)
    output = transcript.read_bytes()
    required = [b'P 077777  A 000001  B 004002', b'A 000123',
                b'P 000101  A 000124', b'P 000102  A 000124']
    if not all(marker in output for marker in required):
        result['status'] = 'FAIL'
    result.update(rom_sha256=hashlib.sha256(image.read_bytes()).hexdigest(), lanes=lanes,
                  console=str(transcript), firmware_patched=False,
                  diagnostic_bootstrap='NOT_RUN (see run_hpi.py)')
    summary = {'status': 'PASS' if all(r['status'] == 'PASS' for r in results) else 'FAIL',
               'cases': cases, 'results': results, 'full_KERN_pass': False}
    (args.output / 'results.json').write_text(json.dumps(summary, indent=2) + '\n')
    for result in results:
        print(result['status'], result['test'])
    return int(summary['status'] != 'PASS')


if __name__ == '__main__':
    raise SystemExit(main())
