"""Configure the original XL BOOTEX using 92071-18090 (INSTL Rev.2213).

Only the documented driver parameter words and installer marker are changed.
No instructions or SYSTEM contents are patched. The original boot extension
performs all loading, relinking, partition allocation and swap initialization.
"""
import hashlib
import struct


def snapshot_symbols(payload):
    offset, result = 0, {}
    while offset + 2 <= len(payload):
        count = int.from_bytes(payload[offset:offset + 2], 'big')
        offset += 2
        if count == 65535:
            return result
        record = payload[offset:offset + count * 2]
        offset += count * 2
        if len(record) != count * 2 or int.from_bytes(payload[offset:offset + 2], 'big') != count:
            raise ValueError('invalid SNAP record')
        offset += 2
        if count == 6:
            words = struct.unpack('>6H', record)
            name = record[2:8].decode('ascii', errors='replace').rstrip()
            result[name] = words[5]
    raise ValueError('missing SNAP EOF')


def install_parameters(original, system, snapshot, lu):
    symbols = snapshot_symbols(snapshot)
    words = struct.unpack('>' + str(len(system) // 2) + 'H', system)
    if int.from_bytes(snapshot[:2], 'big') != 20:
        raise ValueError('not an XL snapshot header')
    header = struct.unpack('>20H', snapshot[2:42])
    if words[symbols['$CKSM']] != header[8] or words[symbols['$SCCK']] != header[9]:
        raise ValueError('SYSTEM does not match SNAP')
    # INSTL DSKAD/FDVT: SYSTEM is word-addressed from zero; DVT word 6
    # supplies device type, and words 23..30 are the eight parameters.
    lut = words[symbols['$LUTA']]
    if not 1 <= lu <= words[symbols['$LUT#']]:
        raise ValueError('LU outside generated table')
    dvt = words[lut + lu - 1]
    kind = (words[dvt + 5] & 0o37400) // 256
    if not 0o30 <= kind <= 0o37:
        raise ValueError('LU is not a disk')
    parameters = list(words[dvt + 22:dvt + 30]) + [kind]
    if len(original) != 65536 or int.from_bytes(original[4:6], 'big') != 0o124003:
        raise ValueError('not an original XL BOOTEX')
    image = bytearray(original)
    for i, word in enumerate(parameters):
        image[(0o100 + i) * 2:(0o101 + i) * 2] = word.to_bytes(2, 'big')
    image[-2:] = (0o46062).to_bytes(2, 'big')
    allowed = set(range(0o100 * 2, 0o111 * 2)) | {65534, 65535}
    if any(a != b and i not in allowed for i, (a, b) in enumerate(zip(original, image))):
        raise ValueError('installer modified code outside documented fields')
    return bytes(image), dict(method='92071-18090 Rev.2213 parameter installation',
        lu=lu, dvt=dvt, parameters=parameters, original_sha256=hashlib.sha256(original).hexdigest(),
        installed_sha256=hashlib.sha256(image).hexdigest(), instructions_unchanged=True)
