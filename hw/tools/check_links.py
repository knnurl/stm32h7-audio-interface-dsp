"""Checks the cables between the rev A boards against hw/tools/links.py, from KiCad's own
netlists of the drawn schematics (not from the Python that generated them).

    python hw/tools/check_links.py

For each link, at both ends: the connector whose Value is the link's name exists once, and each
pin sits on the net the table names (or on no net, for the table's unconnected pins). Exit
status 1 on any difference.
"""
import pathlib
import subprocess
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from kisch import HW, KICAD_CLI, find, find1, parse  # noqa: E402
from links import ENDS, LINKS  # noqa: E402

BOARD_DIRS = {"rev_a_d": "d", "rev_a_a": "a", "rev_a_pl": "pl", "rev_a_pr": "pr"}


def netlist(board):
    d = HW / "rev-a" / BOARD_DIRS[board]
    out = d / f"{board}.net"
    subprocess.run([str(KICAD_CLI), "sch", "export", "netlist", "-o", str(out),
                    str(d / f"{board}.kicad_sch")], check=True, capture_output=True)
    tree = parse(out.read_text(encoding="utf-8"))
    values = {find1(c, "ref")[1]: find1(c, "value")[1]
              for c in find(find1(tree, "components"), "comp")}
    pin_net = {}
    for net in find(find1(tree, "nets"), "net"):
        name = find1(net, "name")[1].lstrip("/")
        if name.startswith("unconnected-"):
            continue
        for n in find(net, "node"):
            pin_net[(find1(n, "ref")[1], find1(n, "pin")[1])] = name
    return values, pin_net


def main():
    cache = {}
    problems = []
    for link, table in LINKS.items():
        for board in ENDS[link]:
            if board not in cache:
                cache[board] = netlist(board)
            values, pin_net = cache[board]
            refs = [r for r, v in values.items() if v == link]
            if len(refs) != 1:
                problems.append(f"{board}: {len(refs)} connectors with Value {link}")
                continue
            ref = refs[0]
            for pin, want in table.items():
                got = pin_net.get((ref, str(pin)))
                if got is not None and "/" in got:
                    got = got.rsplit("/", 1)[1]  # A local net keeps its sheet path.
                if got != want:
                    problems.append(f"{board} {ref} ({link}) pin {pin}: {got!r}, table {want!r}")
        print(f"{link}: checked at {' and '.join(ENDS[link])}")
    for p in problems:
        print("  " + p)
    print("all links match the table" if not problems else f"{len(problems)} differences")
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())
