"""Start the verified RTE-XL 7920 with an ENQ/ACK terminal bridge (macOS/Linux)."""
import argparse
import errno
import json
import os
import pty
import re
import select
import shutil
import sys
import termios
import time
import tty
from pathlib import Path
from firmware import read_pair

ROOT = Path(__file__).resolve().parents[2]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--image', type=Path)
    parser.add_argument('--source', type=Path, default=ROOT / 'build/hp1000/rte-xl-languages/rte-xl-languages-7920.disc')
    parser.add_argument('--check', action='store_true', help='test boot, BASIC arithmetic and return to FMGR, then exit')
    parser.add_argument('--hp264x-status', action='store_true',
                        help='answer HP264x primary status queries for line-mode EDIT; does not emulate a screen')
    args = parser.parse_args()
    image = (args.image or ROOT / ('build/hp1000/rte-xl-console-check/disk.disc' if args.check
                                  else 'build/hp1000/rte-xl-user/rte-xl-7920.disc')).resolve()
    image.parent.mkdir(parents=True, exist_ok=True)
    if not image.exists():
        source = args.source.resolve()
        if not source.exists():
            parser.error('build the language image first; see docs/README.md')
        if source == (ROOT / 'build/hp1000/rte-xl-languages/rte-xl-languages-7920.disc'):
            result = source.parent / 'results.json'
            if not result.exists() or json.loads(result.read_text())['status'] != 'PASS':
                parser.error('the language-image validation must pass before creating a user disk')
        shutil.copyfile(source, image)
        print(f'Created working disk: {image}', flush=True)
    directory = image.parent
    rom = directory / 'processor-rom.bin'
    source = ROOT / 'hp1000-references/software/diagnostics/archives/type-4'
    words, _ = read_pair(source / '12001-16001_Rev-2140.src', source / '12001-16002_Rev-2150.src')
    rom.write_bytes(b''.join(w.to_bytes(2, 'big') for w in words))
    script = directory / 'start.ini'
    script.write_text('\n'.join(['set on', 'on error exit 1', 'set console DBGINT=34', 'set cpu 1000-L,256K',
        'set ASI enabled', 'set HPI enabled', 'set HPI HARDDISK', 'set DA enabled',
        'set DA0 7920', f'attach DA0 {image}', f'set cpu LROM={rom}', 'deposit S 400',
        'reset -p', 'on error ignore', 'step 50000000', 'on error exit 1',
        'assert LSTATUS=207', r'send after=10000,delay=10000,"\045BDC27BOOT\r"', 'on error ignore', 'go']) + '\n')
    print('Ctrl-E pauses SimH; type CONTINUE to resume or QUIT to exit.', flush=True)
    old_terminal = None
    log = directory / 'console.log'
    received, buffer, pending = bytearray(), bytearray(), bytearray()
    state, next_key = 0, 0.0
    steps = [(b'FMGR : \x11', 'MC,3\r'), (b'FMGR : \x11', 'MC,4\r'),
             (b'FMGR : \x11', 'DL,::32002\r'), (b'FMGR : \x11', 'DU,&ASM::32002,1\r')]
    if args.check:
        from rte_7920 import read_volume
        existing = read_volume(image, 1)
        for name in ['DEMLST', 'DEMOBJ', 'DEMO']:
            if name in existing:
                steps.append((b'FMGR : \x11', f'PU,{name}::32002\r'))
        assembly = ("MACRO,R,L\n      NAM DEMO,3,99\n      EXT REIO,EXEC\n"
            "DEMO  JSB REIO\n      DEF *+5\n      DEF TWO\n      DEF ONE\n"
            "      DEF MSG\n      DEF LEN\n      JSB EXEC\n      DEF *+2\n"
            "      DEF SIX\nONE   DEC 1\nTWO   DEC 2\nSIX   DEC 6\n"
            "LEN   DEC -16\nMSG   ASC 8,HELLO FROM MACRO\n      END DEMO\n")
        link = 'SN,SNAP::32001\n' + ''.join(f'LI,{n}::32001\n' for n in
            ['$SYSLB', '$FMP', '$MLIB1', '$MLIB2', '$MXLB'])
        link += 'OU,DEMO::32002\nRE,DEMOBJ::32002\nEN\n'
        from rte_xl_put_text import put_text
        for filename, content, guest in [('demo.mac', assembly, '&DEMO'), ('demo.ld', link, 'DEMLD')]:
            host_file = directory / filename
            host_file.write_text(content)
            put_text(image, host_file, guest, replace=True)
        steps += [
                  (b'FMGR : \x11', 'RU,MACRO::32002,&DEMO::32002,DEMLST::32002,DEMOBJ::32002\r'),
                  (b'FMGR : \x11', 'RU,LOADR,DEMLD::32002\r'),
                  (b'FMGR : \x11', 'RU,DEMO::32002\r')]
    steps += [(b'FMGR : \x11', 'RU,BASIC::32003\r'),
             (b'>\x11', '10 PRINT 6*7\r'), (b'>\x11', '20 END\r'),
             (b'>\x11', 'RUN\r'), (b'>\x11', 'BYE\r'),
             (b'FMGR : \x11', '\x05'), (b'sim> ', 'quit\r')]
    pid, master = pty.fork()
    if pid == 0:
        os.chdir(ROOT)
        os.execv(str(ROOT / 'BIN/hp2100'), ['hp2100', str(script)])
    started = time.monotonic()
    terminal_query = bytearray()
    try:
        if not args.check and sys.stdin.isatty():
            old_terminal = termios.tcgetattr(sys.stdin.fileno())
            tty.setraw(sys.stdin.fileno())
        with log.open('wb') as stream:
            while True:
                if args.check and time.monotonic() - started > 180:
                    raise TimeoutError('console check timed out; inspect ' + str(log))
                readers = [master]
                if not args.check:
                    readers.append(sys.stdin.fileno())
                ready, _, _ = select.select(readers, [], [], .005)
                if master in ready:
                    try:
                        data = os.read(master, 65536)
                    except OSError as error:
                        if error.errno == errno.EIO:
                            break
                        raise
                    if not data:
                        break
                    received.extend(data)
                    stream.write(data)
                    stream.flush()
                    # This is terminal behavior: HP firmware/drivers retain
                    # responsibility for all UART and operating-system I/O.
                    for _ in range(data.count(b'\x05')):
                        os.write(master, b'\x06')
                    if args.hp264x_status:
                        # HP 02645-90005 (Nov.1978), section 6. Preserve
                        # partial queries across PTY reads; the seven status
                        # bytes describe 4KB memory with block/auto-LF off.
                        terminal_query.extend(data)
                        while b'\x1b^\x11' in terminal_query:
                            at=terminal_query.index(b'\x1b^\x11')
                            del terminal_query[:at+3]
                            os.write(master,b'\x1b\\4001468\r')
                        terminal_query[:]=terminal_query[-2:]
                    sys.stdout.buffer.write(data.replace(b'\x05', b'').replace(b'\x00', b''))
                    sys.stdout.buffer.flush()
                    buffer.extend(data)
                if not args.check and sys.stdin.fileno() in ready:
                    data = os.read(sys.stdin.fileno(), 4096)
                    if not data:
                        os.write(master, b'\x05')
                        break
                    os.write(master, data)
                if args.check:
                    if state < len(steps) and not pending:
                        pattern, command = steps[state]
                        where = buffer.find(pattern)
                        if where >= 0:
                            del buffer[:where + len(pattern)]
                            pending.extend(command.encode('ascii'))
                            state += 1
                            next_key = time.monotonic() + .02
                    if pending and time.monotonic() >= next_key:
                        os.write(master, pending[:1])
                        del pending[:1]
                        next_key = time.monotonic() + .005
    finally:
        if old_terminal is not None:
            termios.tcsetattr(sys.stdin.fileno(), termios.TCSADRAIN, old_terminal)
        os.close(master)
        _, status = os.waitpid(pid, 0)
    if args.check:
        passed = (os.waitstatus_to_exitcode(status) == 0 and state == len(steps)
                  and re.search(rb'(?:^|[\r\n])[ \t]*42[ \t]*(?:[\r\n]|$)', received.replace(b'\x05', b''))
                  and b'BASIC READY' in received and b'HELLO FROM MACRO' in received
                  and b'I/O-TO' not in received and b'INVALID COMMAND' not in received and b'ABORTED' not in received and b'NAM HELLO,3,99' in received)
        (directory / 'check.json').write_text(json.dumps(dict(status='PASS' if passed else 'FAIL',
            BASIC_program_6_times_7=passed, host_text_import_and_MACRO_link_run=passed, image=str(image), console=str(log)), indent=2) + '\n')
        return int(not passed)
    return os.waitstatus_to_exitcode(status)


if __name__ == '__main__':
    raise SystemExit(main())
