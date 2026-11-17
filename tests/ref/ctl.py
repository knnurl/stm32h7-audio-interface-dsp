"""Reference models for the control library, in float64: the curves, the MIDI scaling, and the
preset record layout (docs/notes/preset_store.md), written from the notes, not from the C."""
import math
import struct
import zlib

LIN, LOG, VOL, STEP = 0, 1, 2, 3


def clamp(curve, lo, hi, default, v):
    if math.isnan(v):
        return default
    if curve == STEP:
        v = math.floor(v + 0.5)
    return min(max(v, lo), hi)


def from_norm(curve, lo, hi, default, x):
    x = 0.0 if not x > 0 else min(x, 1.0)
    if x == 0.0:
        return lo
    if x == 1.0:
        return hi
    if curve == LOG:
        v = lo * (hi / lo) ** x
    elif curve == VOL:
        v = hi + 60.0 * math.log10(x)
    else:
        v = lo + x * (hi - lo)
    return clamp(curve, lo, hi, default, v)


def to_norm(curve, lo, hi, default, v):
    v = clamp(curve, lo, hi, default, v)
    if curve == LOG:
        x = math.log(v / lo) / math.log(hi / lo)
    elif curve == VOL:
        x = 0.0 if v <= lo else 10 ** ((v - hi) / 60.0)
    else:
        x = (v - lo) / (hi - lo)
    return min(max(x, 0.0), 1.0)


def midi7_to_norm(v):
    return v / 128.0 if v <= 64 else 0.5 + (v - 64) / 126.0


RECORD_MAGIC = 0xC7A1
SECTOR_MAGIC = 0x54455350


def round_word(n):
    return (n + 31) // 32 * 32


def encode_record(slot, seq, name, entries):
    """A record as the store writes it: header, 16-byte name, (id, 0, float32) entries, padded
    with 0xFF to a 32-byte flash word."""
    payload = name.ljust(16, b"\0")[:16]
    for pid, value in entries:
        payload += struct.pack("<HHf", pid, 0, value)
    head = struct.pack("<HBBIHH", RECORD_MAGIC, slot, 1, seq, len(payload), len(entries))
    crc = zlib.crc32(payload, zlib.crc32(head))
    rec = head + struct.pack("<I", crc) + payload
    return rec + b"\xff" * (round_word(len(rec)) - len(rec))


def decode_records(sector):
    """[(offset, slot, seq, name, {id: value}, crc_ok)] up to the first blank or bad header."""
    out = []
    off = 32
    while off + 16 <= len(sector):
        head = sector[off:off + 16]
        if head == b"\xff" * 16:
            break
        magic, slot, ver, seq, plen, count, crc = struct.unpack("<HBBIHHI", head)
        if magic != RECORD_MAGIC or ver != 1 or plen != 16 + 8 * count:
            break
        payload = sector[off + 16:off + 16 + plen]
        ok = zlib.crc32(payload, zlib.crc32(head[:12])) == crc
        values = {}
        for k in range(count):
            pid, _, value = struct.unpack_from("<HHf", payload, 16 + 8 * k)
            values[pid] = value
        out.append((off, slot, seq, payload[:16].rstrip(b"\0"), values, ok))
        off += round_word(16 + plen)
    return out
