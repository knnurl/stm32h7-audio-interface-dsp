"""Runs every DSP self-test case on the Cortex-M4 (through the M7's `m4bench` command) and
compares each output with the PC library by CRC. Prints M4 cycles per frame, and the same in M7
time (the M4 runs at half the M7's clock), and writes a Markdown table if asked.

  python tools/m4_bench.py --port COM22 [--results docs/results/bench_m4.md]
"""
import argparse
import pathlib
import re
import sys
import zlib

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tests"))
sys.path.insert(0, str(ROOT / "tools"))

import dsplib  # noqa: E402
from target_test import command  # noqa: E402

LINE = re.compile(r"^m4bench (?P<name>\S+) ch=(?P<ch>\d+) proc_min=(?P<p>\d+) crc=(?P<crc>[0-9a-f]{8})$")


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--port", required=True)
    ap.add_argument("--results")
    args = ap.parse_args(argv)
    import serial

    lib = dsplib.load()
    host = {}
    for index, name, _ in dsplib.selftest_cases(lib):
        _, y = dsplib.selftest_run(lib, index)
        host[name] = zlib.crc32(y.tobytes())
    with serial.Serial(args.port, 115200, timeout=0.5) as port:
        lines = command(port, "m4bench", "m4bench done", timeout_s=150.0)
    rows, failed = [], False
    for line in lines:
        m = LINE.match(line.strip())
        if not m:
            if line.startswith("m4bench"):
                print(line)
            continue
        name, ch, cycles = m["name"], int(m["ch"]), int(m["p"])
        per_frame = cycles / (dsplib.SELFTEST_FRAMES / ch)
        same = int(m["crc"], 16) == host.get(name)
        failed |= name not in host
        rows.append((name, ch, per_frame, same))
        print(f"{name:20s} {per_frame:8.1f} M4 cycles per frame ({2 * per_frame:8.1f} in M7 time)"
              f"  {'bit-identical' if same else 'differs from the PC'}")
    if args.results and rows:
        out = ["| Case | Channels | M4 cycles per frame | In M7 cycles (x2) | Output vs PC |",
               "|---|---|---|---|---|"]
        for name, ch, pf, same in rows:
            out.append(f"| {name} | {ch} | {pf:.1f} | {2 * pf:.1f} | "
                       f"{'bit-identical' if same else 'differs'} |")
        pathlib.Path(args.results).write_text("\n".join(out) + "\n", encoding="utf-8")
        print(f"table written to {args.results}")
    return 1 if failed or not rows else 0


if __name__ == "__main__":
    sys.exit(main())
