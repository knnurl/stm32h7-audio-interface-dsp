"""Runs the DSP self-test cases on the board and compares them with the PC library.

    python tools/target_test.py --port COM5 [--results docs/results/bench_b1.md]

Fixed-point cases must match by checksum. Float cases are dumped and must be within -120 dBFS
of the PC library. Prints one line per case, and the cycle table. Exit code 0 only when every
case passes.
"""
import argparse
import pathlib
import sys
import time

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tests"))
sys.path.insert(0, str(ROOT / "tools"))

import dsplib  # noqa: E402
import target_protocol as protocol  # noqa: E402


def command(port, text, end_marker, timeout_s=20.0):
    """Sends a command and returns the lines up to the one that starts with `end_marker`."""
    port.reset_input_buffer()
    port.write((text + "\r\n").encode())
    lines, deadline = [], time.time() + timeout_s
    while time.time() < deadline:
        raw = port.readline()
        if not raw:
            continue
        line = raw.decode(errors="replace").strip()
        lines.append(line)
        if line.startswith(end_marker) or line.startswith("error"):
            return lines
    raise TimeoutError(f"no '{end_marker}' after '{text}' within {timeout_s} s")


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--port", required=True, help="the ST-LINK virtual COM port, e.g. COM5")
    parser.add_argument("--results", help="write the cycle table to this Markdown file")
    args = parser.parse_args()

    import serial

    lib = dsplib.load()
    host = {name: (index, fmt) for index, name, fmt in dsplib.selftest_cases(lib)}

    with serial.Serial(args.port, 115200, timeout=0.5) as port:
        info = command(port, "info", "info done")
        for line in info:
            print("  " + line)
        benches = protocol.parse_bench(command(port, "bench", "bench done", timeout_s=60.0))

        failed = False
        seen = set()
        rows = []
        for bench in benches:
            seen.add(bench.name)
            if bench.name not in host:
                print(f"FAIL {bench.name}: not in the PC library (rebuild one side)")
                failed = True
                continue
            index, fmt = host[bench.name]
            _, expected = dsplib.selftest_run(lib, index)
            if fmt == dsplib.FMT_Q31:
                ok, message = protocol.compare_fixed(bench, expected)
            else:
                _, words = protocol.parse_vec(command(port, f"vec {bench.name}", "end"))
                ok, message, _ = protocol.compare_float(words, expected)
            print(f"{'ok  ' if ok else 'FAIL'} {bench.name}: {message}; "
                  f"{bench.cycles_per_sample:.1f} cycles per sample")
            failed = failed or not ok
            rows.append(bench)
        for name in host:
            if name not in seen:
                print(f"FAIL {name}: the target did not run it")
                failed = True

    if args.results and rows:
        lines = ["| Case | Format | Cycles per sample (min) | Median | Max | Frames |",
                 "|---|---|---|---|---|---|"]
        for bench in rows:
            lines.append(f"| {bench.name} | {bench.fmt} | {bench.cycles_per_sample:.1f} | "
                         f"{bench.cycles_med / bench.frames:.1f} | "
                         f"{bench.cycles_max / bench.frames:.1f} | {bench.frames} |")
        pathlib.Path(args.results).write_text("\n".join(lines) + "\n", encoding="utf-8")
        print(f"cycle table written to {args.results}")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
