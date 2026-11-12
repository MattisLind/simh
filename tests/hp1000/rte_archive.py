"""Package unchanged FMP file extents for HP's original SAVER/READR utilities.

Format references: 92068-18053 Rev.5010 tape header/directory and
92068-18054 Rev.2241 JREAD (raw type-1 file access). This constructs an
interchange tape, not executable code or an operating-system image.
"""
import hashlib
import struct
from rte_disk import inspect


def saver_tape(image, destination, extra_files=()):
    directory = inspect(image)
    original = image.read_bytes()
    files = [dict(entry) for entry in directory['files'] if entry['type'] == 5]
    payloads = {entry['name']: original[entry['offset']:entry['offset'] + entry['bytes']]
                for entry in files}
    for name, kind, payload in extra_files:
        if name in payloads:
            raise ValueError('duplicate archive filename')
        files.append(dict(name=name, type=kind, bytes=len(payload),
                          sha256=hashlib.sha256(payload).hexdigest(), generated_input=True))
        payloads[name] = payload
    blocks = sum((entry['bytes'] + 255) // 256 for entry in files)
    header = (' <<RTE FILE SAVE 0800 03AUG78. ' + f'{len(files):5d}'
              + ' FILES.' + f'{blocks:7d}.' + 'BLOCKS  R=1024.  REEL=  1>>1>')
    if len(header) != 80:
        raise ValueError('SAVER header exceeds supported field widths')
    with destination.open('wb') as stream:
        def record(data):
            stream.write(struct.pack('<I', len(data)))
            stream.write(data)
            if len(data) & 1:
                stream.write(b'\0')
            stream.write(struct.pack('<I', len(data)))

        def mark():
            stream.write(bytes(4))

        record(header.encode('ascii'))
        for index, entry in enumerate(files, 1):
            size = (entry['bytes'] + 255) // 256
            name = entry['name']
            if len(name) > 6 or not name.isascii():
                raise ValueError('unsupported FMP name')
            line = f' {index:6d} {name:6}:      :    SC:{entry["type"]:6d}:{size:6d}:{0:6d} '
            if len(line) != 50:
                raise ValueError('SAVER directory entry exceeds supported widths')
            record(line.encode('ascii'))
        mark()
        for entry in files:
            payload = payloads[entry['name']]
            if hashlib.sha256(payload).hexdigest() != entry['sha256']:
                raise ValueError('source file changed during archive creation')
            payload += bytes((-len(payload)) % 256)
            for offset in range(0, len(payload), 2048):
                record(payload[offset:offset + 2048])
            mark()
        mark()
    return dict(source=str(image), source_sha256=directory['sha256'], files=files,
                tape=str(destination), tape_sha256=hashlib.sha256(destination.read_bytes()).hexdigest(),
                format='HP SAVER/READR interchange, raw file extents',
                destination_cartridge='SC', software_patched=False)
