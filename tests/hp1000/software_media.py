"""Read supplied FMP media and preserve every file extent for installation.

D.RTR 92071-18037 EXOPN encodes the extent in the high byte of word 5.
This transport joins successive extents in logical order; it never changes
relocatable records or implements a guest linker.
"""
import hashlib
import struct
from pathlib import Path


def sector_stream(path):
    """Read the checked LibDsk extractor's per-sector records."""
    raw = path.read_bytes()
    offset, sectors, errors = 0, {}, []
    while offset < len(raw):
        cylinder, head, sector, size, status = struct.unpack('<5I', raw[offset:offset + 20])
        offset += 20
        payload = raw[offset:offset + size]
        offset += size
        if len(payload) != size or (cylinder, head, sector) in sectors:
            raise ValueError('truncated or duplicate sector')
        sectors[cylinder, head, sector] = payload
        if status:
            errors.append(dict(cylinder=cylinder, head=head, sector=sector, status=status))
    return sectors, errors


def fmp_files(data, sectors_per_track, header_track):
    """Read a supplied single-directory-track FMP image with known geometry."""
    track_bytes = sectors_per_track * 128
    header_offset = header_track * track_bytes
    header = struct.unpack('>16H', data[header_offset:header_offset + 32])
    if (header[6] & 255) != sectors_per_track or header[7] != header_track or header[8] != 65535:
        raise ValueError('unsupported FMP cartridge header')
    pieces = {}
    stride = header[6] >> 8 or 14
    for n in range(sectors_per_track // 2):
        for i in range(8):
            offset = header_offset + (n * stride % sectors_per_track) * 128 + i * 32
            if offset == header_offset:
                continue
            record = data[offset:offset + 32]
            if record[:2] == b'\xff\xff':
                continue
            if record[:2] == b'\0\0':
                continue
            words = struct.unpack('>16H', record)
            name = record[:6].decode('ascii').rstrip()
            kind, track, packed_sector, count = words[3:7]
            extent, sector = divmod(packed_sector, 256)
            begin = track * track_bytes + sector * 128
            end = begin + count * 128
            if sector >= sectors_per_track or end > header_offset:
                raise ValueError('file exceeds data region')
            if extent in pieces.setdefault(name, {}):
                raise ValueError('duplicate extent')
            pieces[name][extent] = (kind, data[begin:end])
    result = {}
    for name, extents in pieces.items():
        if set(extents) != set(range(len(extents))):
            raise ValueError('missing file extent')
        kinds = {kind for kind, _ in extents.values()}
        if len(kinds) != 1:
            raise ValueError('inconsistent file type across extents')
        result[name] = (kinds.pop(), b''.join(extents[i][1] for i in range(len(extents))))
    return result


def fortran_media(directory=Path('build/hp1000/language-media')):
    sectors, errors = sector_stream(directory / 'FORT77.sectors')
    if errors:
        raise ValueError('Fortran media has unreadable sectors')
    raw = b''.join(sectors[c, h, s] for c in range(35) for h in range(2) for s in range(16))
    return fmp_files(raw, 32, 65)


def basic_media():
    path = Path('hp1000-references/software/operating-systems/92076-13401_BASIC-1000L_REV2326.hpi')
    return fmp_files(path.read_bytes(), 60, 133)
