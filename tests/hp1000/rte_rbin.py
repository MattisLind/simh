"""Validate HP relocatable binary records and wrap them as FMP type-5 records.

The archive stream's first byte counts 16-bit words INCLUDING its three-word
header. Words and checksums are big-endian. The checksum equals the modulo-65536
sum of the record type/control word and payload (the count and checksum are
excluded). RTE disk files add a BE word-count prefix/trailer around each entire
unchanged archive record, then FMP EOF and sector padding.
"""
import hashlib
import struct


def records(data):
    offset, result = 0, []
    while offset < len(data):
        count = data[offset]
        if count < 3:
            raise ValueError(f'invalid record word count at {offset}')
        end = offset + count * 2
        if end > len(data):
            raise ValueError(f'truncated record at {offset}')
        record = data[offset:end]
        words = struct.unpack(f'>{count}H', record)
        if (sum(words[1:]) - 2 * words[2]) & 65535:
            raise ValueError(f'checksum mismatch at {offset}')
        result.append(record)
        offset = end
    if not result:
        raise ValueError('empty relocatable')
    return result


def encode(data):
    items = records(data)
    output = bytearray()
    names = []
    for record in items:
        count = (len(record) // 2).to_bytes(2, 'big')
        output += count + record + count
        if record[2] >> 5 == 1:
            names.append(record[6:12].decode('ascii').rstrip())
    output += b'\xff\xff'
    output += bytes(-len(output) % 256)
    if decode(output) != data:
        raise ValueError('relocatable record round-trip failed')
    return bytes(output), dict(archive_sha256=hashlib.sha256(data).hexdigest(),
        fmp_sha256=hashlib.sha256(output).hexdigest(), records=len(items),
        module_names=names, compressed_records=sum(r[2] >> 5 == 7 for r in items))


def decode(data):
    result, offset = bytearray(), 0
    while offset + 2 <= len(data):
        count = int.from_bytes(data[offset:offset + 2], 'big')
        offset += 2
        if count == 65535:
            # Allocation padding is not a record and can retain old disk
            # contents in a guest-written file. Do not interpret it as data.
            records(result)
            return bytes(result)
        end = offset + count * 2
        if end + 2 > len(data) or int.from_bytes(data[end:end + 2], 'big') != count:
            raise ValueError('invalid FMP record envelope')
        result += data[offset:end]
        offset = end + 2
    raise ValueError('missing FMP EOF')
