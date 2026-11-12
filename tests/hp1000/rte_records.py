"""Encode/decode FMP type-3 variable-length ASCII records (big-endian words)."""


def encode_text(text):
    result = bytearray()
    for line in text.splitlines():
        payload = line.encode('ascii')
        payload += b' ' * (len(payload) % 2)
        count = (len(payload) // 2).to_bytes(2, 'big')
        result += count + payload + count
    result += b'\xff\xff'
    result += bytes(-len(result) % 256)
    return bytes(result)


def decode_text(data):
    records = []
    offset = 0
    while offset + 2 <= len(data):
        count = int.from_bytes(data[offset:offset + 2], 'big')
        offset += 2
        if count == 65535:
            return '\n'.join(records) + '\n'
        end = offset + count * 2
        if end + 2 > len(data) or int.from_bytes(data[end:end + 2], 'big') != count:
            raise ValueError('incomplete FMP record or mismatching trailer')
        records.append(data[offset:end].decode('ascii').rstrip(' '))
        offset = end + 2
    raise ValueError('missing FMP end-of-file marker')
