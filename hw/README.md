# Rev A hardware

Batch 5, stage 3: the schematics. Four KiCad 10 projects, one per board
(`docs/notes/rev_a_board_split.md`):

| Folder | Board | Layers |
|---|---|---|
| `rev-a/d/` | D, power and digital, over the Nucleo | 4 |
| `rev-a/a/` | A, converter and analogue | 4 |
| `rev-a/pl/` | PL, panel left | 2 |
| `rev-a/pr/` | PR, panel right | 2 |

## How the schematics are made

Each board's circuit is written in Python (`rev-a/<board>/design.py`): every part, the net on
each of its pins, and the pins left open. `tools/kisch.py` draws it as a KiCad project, one
sub-sheet per block, with every pin on a short wire and a label, so the connectivity is exactly
the Python's. It refuses a pin that is neither connected nor marked open, a missing footprint, or
a net with one pin. KiCad's ERC then checks the drawing.

    python hw/tools/make_lib.py          (the custom symbols, hw/lib/rev_a.kicad_sym)
    python hw/rev-a/a/design.py          (writes and checks board A; likewise d, pl, pr)
    python hw/tools/check_links.py       (the cables: both ends against tools/links.py)

KiCad 10 must be installed (`%LOCALAPPDATA%\Programs\KiCad\10.0`, or set `KICAD10_DIR`).
**Close a project in KiCad before regenerating it**, then reload.

**Python is the source of truth until the owner signs off the schematic review.** After that the
KiCad files are, and the generator is not run on them again: the owner's edits in KiCad (tidying
the drawing, stage 4 changes) would be lost.

The drawing is plain: parts in rows by block, nets joined by name. It is meant to be read with
KiCad's net highlighting (click a label) and the netlist, not as a hand-drawn circuit diagram.

## Conventions

- Net names: upper case, `_` between words; rails `5V_DIG`, `5V5_PRE`, `+15V_RAW`, `-15V_RAW`,
  `+12V_ANA`, `-12V_ANA`, `5V_ANA`, `3V3_A`, `12V_P`, `NUCLEO_3V3`; one circuit ground `GND` per
  board, `CHASSIS` for the chassis strip.
- Nets on the cables are named exactly as in `tools/links.py`; each connector's Value is the
  cable's name (`J_LINK`, `J_PANEL`, `J_PJ`, `J_HP`) so `check_links.py` can find it.
- Passives 0603 unless a value or rating needs larger; electrolytics and the parts fitted by
  hand say so in a `Fit` field (`hand`).
- Unverified pin-outs: the custom symbols' descriptions say "PIN NUMBERS UNVERIFIED" where the
  datasheet gave them only in a drawing; the schematic review lists them.
