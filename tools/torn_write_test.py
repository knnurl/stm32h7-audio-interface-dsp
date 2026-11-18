"""The preset store's torn-write test (SPEC V18), with no cable to pull.

Each round sends `ptear n`: the M7 starts its independent watchdog with n x 125 us on it and saves
preset 2, so the chip resets n counts into the save, wherever the flash write has got to. The
ST-LINK's serial port stays up through the reset. After the start-up banner the script checks:
- the reset was the watchdog's (`flashinfo` reset_iwdg=1) and no fault was recorded;
- the store mounted and slot 2 holds the old name or the new one, never anything else;
- the evidence of a torn write at this start-up: reads that met an ECC error (ecc_single,
  ecc_double) or a record the scan could not walk past (needs_compact=1).

The store's own `flash_errors` (stat) counts failed programs and erases only, so it is not the
evidence here. A record write takes about 4.5 ms (36 counts), and a save that needs a compaction
erases a sector first; the default sweep, n = 1 to 48, lands resets before, inside and after the
write. A torn record flags the store for compaction, so before each round a plain save lets that
compaction finish (--no-heal skips it, and the resets then all land in the erase instead).

  python tools/torn_write_test.py --port COM22
  python tools/torn_write_test.py --port COM22 --first 10 --last 20 --repeat 3
"""
import argparse
import re
import sys
import time

from ctl import SerialLink, command

SLOT = 2


def slot_name(link):
    final, rows, _ = command(link, "preset list")
    for row in rows:
        m = re.match(rf"{SLOT} seq=\d+ (\S+)", row)
        if m:
            return final, m.group(1)
    return final, None


def read_line_starting(link, prefix, timeout_s):
    end = time.monotonic() + timeout_s
    while time.monotonic() < end:
        line = link.read_line(0.2)
        if line and line.startswith(prefix):
            return line
    return None


def fields(line):
    return {k: int(v) for k, v in re.findall(r"(\w+)=(-?\d+)", line or "")}


def heal(link):
    """A torn record leaves the store flagged for compaction, and the next save then erases a
    sector first (about 1 s): a ptear would only ever land in that erase. A plain save lets the
    compaction finish, so the round starts clean. Returns the flashinfo fields afterwards."""
    link.send("flashinfo")
    info = fields(read_line_starting(link, "flashinfo", 3.0))
    if info.get("needs_compact") == 1:
        final, _, _ = command(link, f"preset save {SLOT} heal", timeout_s=5.0)
        if final is None or not final.startswith(f"ok preset save {SLOT}"):
            raise RuntimeError(f"the healing save failed: {final}")
        link.send("flashinfo")
        info = fields(read_line_starting(link, "flashinfo", 3.0))
        if info.get("needs_compact") != 0:
            raise RuntimeError("still flagged for compaction after a save")
        info["healed"] = 1
    return info


def one_round(link, n, clean):
    healed = heal(link).get("healed", 0) if clean else 0
    _, before = slot_name(link)
    new = f"tear{n:04d}"
    link.send(f"ptear {n}")
    armed = read_line_starting(link, "ptear armed", 2.0)
    finished = False
    booted = False
    end = time.monotonic() + 8.0
    while time.monotonic() < end:
        line = link.read_line(0.2)
        if not line:
            continue
        if line.startswith("ptear save finished first"):
            finished = True
        if line.startswith("info done"):
            booted = True
            break
    if armed is None or not booted:
        return {"n": n, "ok": False, "why": "no ptear line" if armed is None else "no restart"}
    time.sleep(0.3)
    link.send("fault")
    fault = read_line_starting(link, "fault", 3.0)
    link.send("flashinfo")
    info = fields(read_line_starting(link, "flashinfo", 3.0))
    final, after = slot_name(link)
    torn = info.get("ecc_single", 0) + info.get("ecc_double", 0) > 0 or info.get(
        "needs_compact", 0) == 1
    # A save that reported finishing must have kept its record; one cut short keeps either.
    allowed = {new} if finished else {before, new}
    ok = (fault == "fault none" and info.get("reset_iwdg") == 1 and final is not None
          and final.startswith("ok preset list") and after in allowed)
    return {"n": n, "ok": ok, "finished": finished, "before": before, "after": after,
            "fault": fault, "info": info, "torn": torn, "healed": healed}


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--port", required=True)
    ap.add_argument("--first", type=int, default=1)
    ap.add_argument("--last", type=int, default=48)
    ap.add_argument("--repeat", type=int, default=1)
    ap.add_argument("--no-heal", action="store_true",
                    help="leave a torn store as it is (resets then land in the compaction's erase)")
    args = ap.parse_args(argv)

    link = SerialLink(args.port)
    time.sleep(0.5)
    results = []
    for _ in range(args.repeat):
        for n in range(args.first, args.last + 1):
            r = one_round(link, n, not args.no_heal)
            results.append(r)
            if "why" in r:
                print(f"n={n:3d} FAIL: {r['why']}")
                continue
            i = r["info"]
            kept = "new" if r["after"] == f"tear{n:04d}" else (
                "old" if r["after"] == r["before"] else f"OTHER {r['after']}")
            print(f"n={n:3d} {'PASS' if r['ok'] else 'FAIL'}: slot {SLOT} {kept}; "
                  f"{'save finished first' if r['finished'] else 'reset inside the save'}; "
                  f"ecc single={i.get('ecc_single')} double={i.get('ecc_double')} "
                  f"needs_compact={i.get('needs_compact')} compactions={i.get('compactions')}"
                  f"{'  TORN' if r['torn'] else ''}{'  (healed first)' if r['healed'] else ''}; "
                  f"{r['fault']}")
    passed = sum(r["ok"] for r in results)
    inside = sum(1 for r in results if "why" not in r and not r["finished"])
    torn = sum(1 for r in results if r.get("torn"))
    print(f"{passed} of {len(results)} rounds passed; {inside} reset inside the save; "
          f"{torn} start-ups found a torn record")
    if not torn:
        print("no start-up found a torn record: the ECC path is still not exercised")
    return 0 if passed == len(results) else 1


if __name__ == "__main__":
    sys.exit(main())
