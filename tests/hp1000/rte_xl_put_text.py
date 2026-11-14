"""Import host ASCII text into a stopped, working RTE-XL 7920 image."""
import argparse
import os
import struct
import tempfile
from pathlib import Path
from rte_7920 import volume_geometry, HEADS, TRACK_BYTES, read_volume
from rte_records import encode_text, decode_text


def put_text(image, source, name, volume=1, replace=False):
    image = image.resolve()
    if 'hp1000-references' in image.parts:
        raise ValueError('use a working disk, not original reference media')
    if not name.isascii() or not 1 <= len(name) <= 6 or any(c.isspace() for c in name):
        raise ValueError('file name must contain 1..6 ASCII characters without spaces')
    text = source.read_text(encoding='ascii').replace('\r\n', '\n').replace('\r', '\n')
    payload = encode_text(text)
    raw = image.read_bytes()
    if len(raw) != 823 * HEADS * TRACK_BYTES:
        raise ValueError('not a raw 7920 image')
    data = bytearray(raw)
    data[::2], data[1::2] = raw[1::2], raw[::2]
    geometry = volume_geometry(volume)
    base = geometry['start_cylinder'] * HEADS * TRACK_BYTES
    header_offset = base + (geometry['tracks'] - 1) * TRACK_BYTES
    header = list(struct.unpack('>16H', data[header_offset:header_offset + 32]))
    if (header[6] & 255) != 96 or header[7] != geometry['tracks'] - 1 or header[8] != 65535:
        raise ValueError('unsupported directory geometry')
    end = header[9] * TRACK_BYTES + header[5] * 128
    matches, free = [], []
    stride = header[6] >> 8 or 14
    for n in range(48):
        for i in range(8):
            offset = header_offset + n * stride % 96 * 128 + i * 32
            if offset == header_offset:
                continue
            record = data[offset:offset + 32]
            if record[:2] in [b'\0\0', b'\xff\xff']:
                free.append(offset)
                continue
            words = struct.unpack('>16H', record)
            extent, sector = divmod(words[5], 256)
            if words[4] * TRACK_BYTES + sector * 128 + words[6] * 128 > end:
                raise ValueError('allocation pointer precedes live file data')
            if record[:6].decode('ascii').rstrip() == name:
                matches.append((offset, extent))
    if matches and not replace:
        raise ValueError('file exists; use --replace to replace its text')
    if len(matches) > 1 or (matches and matches[0][1] != 0):
        raise ValueError('replacing a file with multiple extents is unsupported')
    if not matches and not free:
        raise ValueError('directory full')
    if end + len(payload) > header[7] * TRACK_BYTES:
        raise ValueError('not enough unallocated space; compact the cartridge in RTE first')
    slot = matches[0][0] if matches else free[0]
    if matches and int.from_bytes(data[slot + 6:slot + 8], 'big') not in (3, 4):
        raise ValueError('only ASCII files may be replaced by this importer')
    record = bytearray(data[slot:slot + 32]) if matches else bytearray(32)
    track, sector = divmod(end // 128, 96)
    record[:14] = name.ljust(6).encode('ascii') + struct.pack('>4H', 3, track, sector, len(payload) // 128)
    data[slot:slot + 32] = record
    data[base + end:base + end + len(payload)] = payload
    header[9], header[5] = divmod((end + len(payload)) // 128, 96)
    data[header_offset:header_offset + 32] = struct.pack('>16H', *header)
    data[::2], data[1::2] = data[1::2], data[::2]
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(dir=image.parent, prefix=image.name + '.', delete=False) as stream:
            temporary = Path(stream.name)
            stream.write(data)
        expected = decode_text(payload)
        if decode_text(read_volume(temporary, volume)[name][1]) != expected:
            raise ValueError('import verification failed')
        os.chmod(temporary, image.stat().st_mode & 0o777)
        os.replace(temporary, image)
        temporary = None
    finally:
        if temporary is not None:
            temporary.unlink()
    return dict(file=name, cartridge_reference=header[3], bytes=len(payload), replaced=bool(matches))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('image', type=Path)
    parser.add_argument('source', type=Path)
    parser.add_argument('--name', required=True)
    parser.add_argument('--volume', type=int, choices=range(10), default=1)
    parser.add_argument('--replace', action='store_true')
    args = parser.parse_args()
    print(put_text(args.image, args.source, args.name.upper(), args.volume, args.replace))


if __name__ == '__main__':
    main()
