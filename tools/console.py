"""A plain serial console for the firmware.

    python tools/console.py --port COM5

Type a command (info, cases, bench, vec <name>, fault, ptime, or any control protocol command:
hello, list, get, set, mode, meters, preset, src, tempo, stat) and press Enter. Ctrl+C leaves.
"""
import argparse
import sys
import threading

import serial


def reader(port):
    while port.is_open:
        try:
            data = port.read(256)
        except serial.SerialException:
            return
        if data:
            sys.stdout.write(data.decode(errors="replace"))
            sys.stdout.flush()


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--port", required=True)
    args = parser.parse_args()
    with serial.Serial(args.port, 115200, timeout=0.1) as port:
        threading.Thread(target=reader, args=(port,), daemon=True).start()
        try:
            for line in sys.stdin:
                port.write((line.strip() + "\r\n").encode())
        except KeyboardInterrupt:
            pass


if __name__ == "__main__":
    main()
