"""The preset store's power-cut test (SPEC V18), with the owner pulling the cable.

Each round: the script saves preset 2 over and over (a record write takes about 4.5 ms), the
owner unplugs the Nucleo's ST-LINK USB cable (its only supply) while it does, then plugs it back
in. The script waits for the port, then checks that the board came up without a fault, that the
store mounted, and that slot 2 holds one of the names it wrote: the last one confirmed or the one
in flight, never anything else. `flash_errors` in `stat` counts the ECC errors the read path met
and masked; a round that cut a write in half shows one there.

  python tools/power_cut_test.py --port COM22 --rounds 5
  python tools/power_cut_test.py --port COM22 --dry-run     (no cut: checks the script itself)
"""
import argparse
import re
import sys
import time

from ctl import SerialLink, command

SLOT = 2


def wait_for_port(port, present, timeout_s):
    from serial.tools import list_ports
    end = time.monotonic() + timeout_s
    while time.monotonic() < end:
        if any(p.device == port for p in list_ports.comports()) == present:
            return True
        time.sleep(0.2)
    return False


def board_state(port):
    """Opens the port after a boot and returns (fault line, stat line, slot-2 name or None)."""
    link = SerialLink(port)
    time.sleep(1.5)  # The banner and the M4's start-up.
    link.send("fault")
    fault = None
    end = time.monotonic() + 3.0
    while time.monotonic() < end and fault is None:
        line = link.read_line(0.2)
        if line and line.startswith("fault"):
            fault = line
    stat, _, _ = command(link, "stat")
    final, rows, _ = command(link, "preset list")
    name = None
    for row in rows:
        m = re.match(rf"{SLOT} seq=\d+ (\S+)", row)
        if m:
            name = m.group(1)
    link.port.close()
    return fault, stat, final, name


def write_until_cut(port, round_no, dry_run):
    """Saves preset 2 until the port goes away. Returns (last confirmed index, last sent index)."""
    link = SerialLink(port)
    confirmed, sent = -1, -1
    print(f"round {round_no}: writing preset {SLOT} over and over. "
          + ("(dry run: stopping after 200 writes)" if dry_run else
             "Unplug the Nucleo's USB cable now."))
    try:
        for i in range(1_000_000):
            sent = i
            # 3 s: a save that triggers a compaction erases a sector first (960 ms measured).
            final, _, _ = command(link, f"preset save {SLOT} r{round_no}w{i:06d}", timeout_s=3.0)
            if final is None:
                break
            if final.startswith(f"ok preset save {SLOT}"):
                confirmed = i
            if dry_run and i >= 199:
                break
    except Exception as exc:  # The port vanishing is the expected way out.
        print(f"  port gone after write {sent} ({type(exc).__name__})")
    try:
        link.port.close()
    except Exception:
        pass
    return confirmed, sent


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--port", required=True)
    ap.add_argument("--rounds", type=int, default=5)
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args(argv)

    failures = 0
    for r in range(1, args.rounds + 1):
        confirmed, sent = write_until_cut(args.port, r, args.dry_run)
        if not args.dry_run:
            if not wait_for_port(args.port, False, 5.0):
                print("  the port is still there: was the cable pulled?")
            print("  plug the cable back in.")
            if not wait_for_port(args.port, True, 120.0):
                print("  no port after 2 minutes; stopping")
                return 1
        fault, stat, final, name = board_state(args.port)
        allowed = {f"r{r}w{i:06d}" for i in (confirmed, confirmed + 1, sent) if i >= 0}
        ok = (fault == "fault none" and final is not None and final.startswith("ok preset list")
              and name in allowed)
        errors = re.search(r"flash_errors=(\d+)", stat or "")
        print(f"  {'PASS' if ok else 'FAIL'}: confirmed write {confirmed}, slot {SLOT} holds "
              f"{name}; {fault}; flash_errors={errors.group(1) if errors else '?'}")
        if not ok:
            print(f"  stat: {stat}\n  preset list: {final}")
            failures += 1
    print(f"{args.rounds - failures} of {args.rounds} rounds passed")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
