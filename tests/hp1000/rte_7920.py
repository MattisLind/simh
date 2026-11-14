"""FMP media transport for DD.30's documented ten-volume HP 7920 layout.

92071-18085 Rev.2326 GEN M7920:0..9 defines the boundaries and directories.
The existing DA backend uses host-order 16-bit sectors; FMP payloads are BE.
"""
import hashlib
import struct

TRACK_BYTES = 48 * 256
CYLINDERS, HEADS = 823, 5


def volume_geometry(volume):
    if not 0 <= volume < 10:
        raise ValueError('invalid 7920 volume')
    return dict(start_cylinder=83 * volume, data_tracks=405 if volume < 9 else 369,
                directory_tracks=1,
                tracks=406 if volume < 9 else 370)


def make_image(path, volumes):
    image = bytearray(CYLINDERS * HEADS * TRACK_BYTES)
    manifest = []
    for volume in range(10):
        geometry = volume_geometry(volume)
        base = geometry['start_cylinder'] * HEADS * TRACK_BYTES
        header_offset = base + (geometry['tracks'] - 1) * TRACK_BYTES
        files = volumes.get(volume, {})
        order = list(files)
        if 'BOOTEX' in order:
            order.remove('BOOTEX')
            order.insert(0, 'BOOTEX')
        # Directory interleave is the standard D.RTR 14-sector stride.
        slots = []
        for track in range(geometry['tracks'] - 1,
                           geometry['data_tracks'] - 1, -1):
            for n in range(48):
                slots.extend(base + track * TRACK_BYTES + (n * 14 % 96) * 128 + i * 32
                             for i in range(8))
        slots = slots[1:]
        if len(order) > len(slots):
            raise ValueError('directory full')
        end, records = 0, []
        for slot, name in zip(slots, order):
            kind, payload = files[name]
            if not name.isascii() or not 1 <= len(name) <= 6 or not payload or len(payload) % 256:
                raise ValueError('invalid FMP input')
            if end + len(payload) > geometry['data_tracks'] * TRACK_BYTES:
                raise ValueError('volume data full')
            track, sector = divmod(end // 128, 96)
            image[slot:slot + 32] = name.ljust(6).encode('ascii') + struct.pack(
                '>13H', kind, track, sector, len(payload) // 128, *([0] * 9))
            image[base + end:base + end + len(payload)] = payload
            records.append(dict(name=name, type=kind, bytes=len(payload),
                offset=base + end, sha256=hashlib.sha256(payload).hexdigest()))
            end += len(payload)
        next_track, next_sector = divmod(end // 128, 96)
        header = b'\xc8PDISK' + struct.pack('>13H', 32001 + volume, 0, next_sector, 96,
            geometry['tracks'] - 1, (-geometry['directory_tracks']) & 65535, next_track, *([0] * 6))
        image[header_offset:header_offset + 32] = header
        manifest.append(dict(volume=volume, cartridge_reference=32001 + volume,
                             geometry=geometry, files=records))
    # DA/disclib serializes host-order HP words. Convert explicitly to LE so
    # this image is deterministic across host architectures.
    little = bytearray(image)
    little[::2], little[1::2] = image[1::2], image[::2]
    path.write_bytes(little)
    return dict(path=str(path), bytes=len(little), sha256=hashlib.sha256(little).hexdigest(),
                format='raw little-endian HP words; DA 7920', volumes=manifest)


def read_volume(path, volume=0):
    """Read a single-directory-track volume from an existing DA image."""
    from software_media import fmp_files
    raw = bytearray(path.read_bytes())
    raw[::2], raw[1::2] = raw[1::2], raw[::2]
    geometry = volume_geometry(volume)
    base = geometry['start_cylinder'] * HEADS * TRACK_BYTES
    return fmp_files(raw[base:], 96, geometry['tracks'] - 1)
