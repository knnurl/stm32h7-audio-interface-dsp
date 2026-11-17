"""The text the firmware prints for `bench` and `vec` (fw/cm7/src/bench.h), parsed and compared
with the PC library. No serial port here, so the unit tests can exercise it with text made from
the PC library itself."""
import re
import zlib
from dataclasses import dataclass

import numpy as np

BENCH_RE = re.compile(
    r"^bench (?P<name>\S+) fmt=(?P<fmt>f32|q31) frames=(?P<frames>\d+) runs=(?P<runs>\d+) "
    r"min=(?P<min>\d+) med=(?P<med>\d+) max=(?P<max>\d+) crc=(?P<crc>[0-9a-fA-F]{8})$"
)
VEC_RE = re.compile(r"^vec (?P<name>\S+) (?P<count>\d+)$")

FLOAT_LIMIT_DB = -120.0


@dataclass
class BenchLine:
    name: str
    fmt: str
    frames: int
    runs: int
    cycles_min: int
    cycles_med: int
    cycles_max: int
    crc: int

    @property
    def cycles_per_sample(self):
        return self.cycles_min / self.frames


def parse_bench(lines):
    """The bench lines among `lines`, in order."""
    found = []
    for line in lines:
        match = BENCH_RE.match(line.strip())
        if match:
            found.append(BenchLine(match["name"], match["fmt"], int(match["frames"]),
                                   int(match["runs"]), int(match["min"]), int(match["med"]),
                                   int(match["max"]), int(match["crc"], 16)))
    return found


def parse_vec(lines):
    """(name, uint32 array) from a `vec` dump. Raises ValueError when it is incomplete."""
    name, count, words, ended = None, 0, [], False
    for line in lines:
        text = line.strip()
        if name is None:
            match = VEC_RE.match(text)
            if match:
                name, count = match["name"], int(match["count"])
            continue
        if text == "end":
            ended = True
            break
        words.extend(int(word, 16) for word in text.split())
    if name is None or not ended or len(words) != count:
        raise ValueError(f"incomplete vector dump: {len(words)} of {count} words")
    return name, np.array(words, dtype=np.uint32)


def host_crc(output):
    """CRC-32 of the output as little-endian 32-bit words, as the firmware computes it."""
    data = np.ascontiguousarray(output)
    return zlib.crc32(data.astype(data.dtype.newbyteorder("<"), copy=False).tobytes())


def compare_fixed(bench, host_output):
    """Fixed point: the target's checksum must equal the PC's. Returns (ok, message)."""
    expected = host_crc(host_output)
    ok = bench.crc == expected
    return ok, f"crc target {bench.crc:08x} host {expected:08x}"


def compare_float(target_words, host_output, limit_db=FLOAT_LIMIT_DB):
    """Float: the target's output must be within the tolerance of the PC's. Returns (ok,
    message, error in dBFS)."""
    target = target_words.view(np.float32)
    if len(target) != len(host_output):
        return False, f"length {len(target)} against {len(host_output)}", 0.0
    if not np.all(np.isfinite(target)):
        return False, "non-finite samples from the target", 0.0
    err = float(np.max(np.abs(target.astype(np.float64) - host_output.astype(np.float64))))
    err_db = -np.inf if err == 0.0 else 20.0 * np.log10(err)
    identical = target.tobytes() == host_output.astype(np.float32).tobytes()
    note = "bit-identical" if identical else f"error {err_db:.1f} dBFS"
    return err_db <= limit_db, f"{note} (limit {limit_db} dBFS)", err_db


def format_bench(name, fmt, output, cycles=(0, 0, 0), runs=33):
    """A bench line as the firmware prints it. For tests."""
    return (f"bench {name} fmt={fmt} frames={len(output)} runs={runs} min={cycles[0]} "
            f"med={cycles[1]} max={cycles[2]} crc={host_crc(output):08x}")


def format_vec(name, output):
    """A vec dump as the firmware prints it. For tests."""
    words = np.ascontiguousarray(output).view(np.uint32)
    lines = [f"vec {name} {len(words)}"]
    for start in range(0, len(words), 8):
        lines.append(" ".join(f"{word:08x}" for word in words[start:start + 8]))
    lines.append("end")
    return lines
