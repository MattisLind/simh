"""Read the supplied BOOTX/FMP HPI master discs without changing them.

Geometry and directory traversal follow 92070-18087 Rev.2001 BOOTX:
header words 11..13, CONT/TCONV/DIREC/FOUND. Directory entries are 16
words; file offsets/sizes use 64-word FMP sectors, not hardware sectors.
This is intentionally limited to the supplied 7902 double-density format.
"""
import argparse
import hashlib
import json
from pathlib import Path


def inspect(path):
    data = path.read_bytes()
    if len(data) != 77 * 2 * 30 * 256:
        raise ValueError('expected 77/2/30/256-byte HPI image')
    words = [int.from_bytes(data[i:i + 2], 'big') for i in range(0, 36, 2)]
    has_bootx = words[0] == 67 and words[12:14] == [30, 2]
    if has_bootx:
        tracks = words[11]
    else:
        # Later masters may be data-only cartridges. Locate their FMP header
        # by its geometry and self-address, rather than assuming a BOOTX.
        candidates = []
        for track in range(154):
            header = data[track * 7680:track * 7680 + 32]
            values = [int.from_bytes(header[i:i + 2], 'big') for i in range(0, 32, 2)]
            if (32000 <= values[3] < 32768 and values[6] == 60
                    and values[7] == track and -154 <= int.from_bytes(header[16:18], 'big', signed=True) < 0):
                candidates.append(track + 1)
        if len(candidates) != 1:
            raise ValueError('no unambiguous supported FMP directory header')
        tracks = candidates[0]
    directory_offset = (tracks - 1) * 7680
    header = data[directory_offset:directory_offset + 32]
    directory_tracks = -int.from_bytes(header[16:18], 'big', signed=True)
    if not 1 <= directory_tracks <= tracks:
        raise ValueError('invalid directory track count')
    entries = []
    for track in range(tracks - 1, tracks - 1 - directory_tracks, -1):
        block = data[track * 7680:(track + 1) * 7680]
        for offset in range(0, len(block), 32):
            if track == tracks - 1 and offset == 0:
                continue
            record = block[offset:offset + 32]
            # D.RTR PURG1/PURG2 marks a reusable entry with -1.
            if record[:2] == b"\xff\xff":
                continue
            if not any(record):
                continue
            fields = [int.from_bytes(record[i:i + 2], 'big') for i in range(6, 18, 2)]
            kind, first_track, first_sector, sectors, word7, word8 = fields
            # D.RTR EXOPN: the high byte is the file extent number.
            extent, first_sector = divmod(first_sector, 256)
            start = first_track * 7680 + first_sector * 128
            end = start + sectors * 128
            if first_sector >= 60 or end > len(data):
                raise ValueError('file extends outside supported image geometry')
            entries.append(dict(name=record[:6].decode('ascii', errors='backslashreplace').rstrip(),
                                type=kind, extent=extent, track=first_track, sector=first_sector,
                                sectors=sectors, descriptor_words_7_8=[word7, word8],
                                offset=start, bytes=end - start,
                                sha256=hashlib.sha256(data[start:end]).hexdigest()))
    return dict(path=str(path), sha256=hashlib.sha256(data).hexdigest(),
                tracks=tracks, directory_tracks=directory_tracks, has_BOOTX=has_bootx,
                has_SYSTEM=any(e['name'] == 'SYSTEM' for e in entries), files=entries)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('image', type=Path)
    parser.add_argument('--output', type=Path)
    args = parser.parse_args()
    result = json.dumps(inspect(args.image), indent=2) + '\n'
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(result)
    else:
        print(result, end='')


def append_files(source, destination, additions):
    """Append to a packed, one-directory-track master without changing old files.

    Implements D.RTR (92070-18037 Rev.2001) DPMM/UDAD/NXT/S/CREA6:
    header words 5/9 are next sector/track; word 6 contains the directory
    sector step (zero defaults to 14) and sectors/track. No fragmented,
    extended, purged, or multi-track directories are supported here.
    """
    import math
    import struct
    directory = inspect(source)
    if source.resolve() == destination.resolve():
        raise ValueError('installation requires a separate working image')
    if directory['directory_tracks'] != 1:
        raise ValueError('only a single directory track is supported')
    if any(entry['extent'] for entry in directory['files']):
        raise ValueError('append does not support file extents')
    data = bytearray(source.read_bytes())
    header_offset = (directory['tracks'] - 1) * 7680
    header = list(struct.unpack('>16H', data[header_offset:header_offset + 32]))
    sectors = header[6] & 255
    stride = header[6] >> 8 or 14
    if sectors != 60 or stride % 2 or math.gcd(stride // 2, sectors // 2) != 1:
        raise ValueError('unsupported directory interleave')
    end = 0
    for entry in sorted(directory['files'], key=lambda e: e['offset']):
        if entry['offset'] != end:
            raise ValueError('master is not packed; fragmented allocation unsupported')
        end += entry['bytes']
    if end != (header[9] * sectors + header[5]) * 128:
        raise ValueError('header allocation pointer does not match file extents')
    slots = []
    for n in range(sectors // 2):
        sector = n * stride % sectors
        slots.extend(header_offset + sector * 128 + i * 32 for i in range(8))
    slots = slots[1:]  # cartridge header is not a file entry
    used = [any(data[offset:offset + 32]) for offset in slots]
    first = next((i for i, occupied in enumerate(used) if not occupied), len(used))
    if any(used[first:]):
        raise ValueError('directory contains holes or reusable entries')
    names = {entry['name'] for entry in directory['files']}
    for name, kind, payload in additions:
        if name in names or not name.isascii() or not 1 <= len(name) <= 6:
            raise ValueError('duplicate or invalid filename')
        if not payload or len(payload) % 256:
            raise ValueError('file must be padded to a 128-word hardware sector')
        if first >= len(slots) or end + len(payload) > header_offset:
            raise ValueError('insufficient directory or data space')
        track, sector = divmod(end // 128, sectors)
        record = name.ljust(6).encode('ascii') + struct.pack('>13H', kind, track,
                    sector, len(payload) // 128, *([0] * 9))
        data[slots[first]:slots[first] + 32] = record
        data[end:end + len(payload)] = payload
        first += 1
        end += len(payload)
        names.add(name)
    header[9], header[5] = divmod(end // 128, sectors)
    data[header_offset:header_offset + 32] = struct.pack('>16H', *header)
    destination.write_bytes(data)
    result = inspect(destination)
    by_name = {entry['name']: entry for entry in result['files']}
    for entry in directory['files']:
        if by_name[entry['name']]['sha256'] != entry['sha256']:
            raise ValueError('installation changed an existing file')
    return result


if __name__ == '__main__':
    main()


def pack_files(template, destination, files, cartridge_reference, first=None):
    """Write complete file payloads into a fresh, contiguous FMP cartridge.

    This is media transport, using the same directory interleave as append_files.
    Callers supply every retained file explicitly. Executables are copied as-is;
    this routine does not generate, link, or modify guest code.
    """
    import struct
    directory = inspect(template)
    if template.resolve() == destination.resolve():
        raise ValueError('packing requires a separate destination')
    if directory['directory_tracks'] != 1:
        raise ValueError('only single-track directories are supported')
    header_offset = (directory['tracks'] - 1) * 7680
    source = template.read_bytes()
    header = list(struct.unpack('>16H', source[header_offset:header_offset + 32]))
    sectors, stride = header[6] & 255, header[6] >> 8 or 14
    if sectors != 60 or not 32000 <= cartridge_reference < 32768:
        raise ValueError('unsupported geometry or cartridge reference')
    slots = []
    for n in range(30):
        slots.extend(header_offset + n * stride % sectors * 128 + i * 32 for i in range(8))
    slots = slots[1:]
    order = list(files)
    if first is not None:
        order.remove(first)
        order.insert(0, first)
    if len(order) > len(slots):
        raise ValueError('directory full')
    data, end = bytearray(len(source)), 0
    for offset, name in zip(slots, order):
        kind, payload = files[name]
        if not name.isascii() or not 1 <= len(name) <= 6 or not payload or len(payload) % 256:
            raise ValueError('invalid file name or unaligned payload')
        if end + len(payload) > header_offset:
            raise ValueError('data area full')
        track, sector = divmod(end // 128, sectors)
        data[offset:offset + 32] = name.ljust(6).encode('ascii') + struct.pack(
            '>13H', kind, track, sector, len(payload) // 128, *([0] * 9))
        data[end:end + len(payload)] = payload
        end += len(payload)
    header[3] = cartridge_reference
    header[9], header[5] = divmod(end // 128, sectors)
    data[header_offset:header_offset + 32] = struct.pack('>16H', *header)
    destination.write_bytes(data)
    result = inspect(destination)
    actual = {entry['name']: entry for entry in result['files']}
    if set(actual) != set(files) or any(actual[name]['sha256'] != hashlib.sha256(payload).hexdigest()
                                      for name, (_, payload) in files.items()):
        raise ValueError('packed file verification failed')
    return result
