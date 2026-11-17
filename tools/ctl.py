"""PC client for the control protocol (docs/notes/control_protocol.md).

Talks to the board over a serial port, or to the C control library on this PC (--sim: the same
code as the firmware, with simulated flash), so it can be tried without hardware.

  python tools/ctl.py --sim list
  python tools/ctl.py --port COM5 get monitor_volume_db
  python tools/ctl.py --port COM5 set tone_bass_db 3
  python tools/ctl.py --port COM5 mode tone_bass_db pc
  python tools/ctl.py --port COM5 preset save 2 "Vocal take"
  python tools/ctl.py --port COM5 preset load 2
  python tools/ctl.py --port COM5 watch          (meters and changes until Ctrl+C)
  python tools/ctl.py --port COM5 raw "stat"

Exit status 0 when the device answered ok, 1 on err, 2 on no answer.
"""
import argparse
import pathlib
import sys
import time

ROOT = pathlib.Path(__file__).resolve().parent.parent


class SimLink:
    """The control library in-process, through tests/ctllib.py."""

    def __init__(self):
        sys.path.insert(0, str(ROOT / "tests"))
        import ctllib
        self.dev = ctllib.Device(ctllib.load())
        self.pending = []

    def send(self, line):
        self.pending += self.dev.send(line + "\n")

    def read_line(self, timeout_s):
        if not self.pending:
            self.pending += self.dev.poll()
        return self.pending.pop(0) if self.pending else None


class SerialLink:
    def __init__(self, port, baud=115200):
        import serial  # pyserial, pinned in tests/requirements.txt
        self.port = serial.Serial(port, baud, timeout=0.05)
        self.buffer = b""

    def send(self, line):
        self.port.write(line.encode("ascii") + b"\r\n")

    def read_line(self, timeout_s):
        end = time.monotonic() + timeout_s
        while time.monotonic() < end:
            if b"\n" in self.buffer:
                line, self.buffer = self.buffer.split(b"\n", 1)
                return line.rstrip(b"\r").decode("ascii", "replace")
            self.buffer += self.port.read(256)
        return None


def command(link, line, timeout_s=3.0):
    """Sends one command. Returns (final line, data lines, unsolicited lines)."""
    link.send(line)
    data, unsolicited = [], []
    end = time.monotonic() + timeout_s
    while time.monotonic() < end:
        reply = link.read_line(0.2)
        if reply is None:
            continue
        if reply.startswith("ok") or reply.startswith("err"):
            return reply, data, unsolicited
        if reply.startswith("= "):
            data.append(reply[2:])
        elif reply.startswith("#"):
            unsolicited.append(reply)
        # Anything else is board console output (banners): ignored.
    return None, data, unsolicited


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    where = ap.add_mutually_exclusive_group(required=True)
    where.add_argument("--port", help="serial port, for example COM5")
    where.add_argument("--sim", action="store_true", help="the C library on this PC")
    ap.add_argument("words", nargs="+", help="command and arguments")
    args = ap.parse_args(argv)
    link = SimLink() if args.sim else SerialLink(args.port)

    if args.words[0] == "watch":
        command(link, "meters on")
        try:
            while True:
                line = link.read_line(1.0)
                if line and line.startswith("#"):
                    print(line, flush=True)
                elif args.sim:
                    time.sleep(0.1)
        except KeyboardInterrupt:
            command(link, "meters off")
            return 0
    line = " ".join(args.words[1:] if args.words[0] == "raw" else args.words)
    final, data, unsolicited = command(link, line, timeout_s=10.0 if "list" in line else 3.0)
    for d in data:
        print(d)
    for u in unsolicited:
        print(u)
    if final is None:
        print("no answer", file=sys.stderr)
        return 2
    print(final)
    return 0 if final.startswith("ok") else 1


if __name__ == "__main__":
    sys.exit(main())
