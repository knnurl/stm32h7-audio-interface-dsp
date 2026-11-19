"""Writes KiCad 10 schematics from a Python netlist (batch 5, stage 3).

A board is described in Python: parts, the net on each pin, and which pins are unconnected. This
module draws it as a KiCad project: one root sheet holding one sub-sheet per block. Every pin
gets a short wire and a label (a local label for a net used on one sheet only, a global label
for a net used on several, a power symbol for a rail), so connectivity is exact and checked by
KiCad's ERC. The drawing is plain: parts in rows, nets by label, no wires between parts.

Python is the source of truth until the owner signs off the schematic review; after that the
KiCad files are, and this generator is not run on them again (hw/README.md).

Symbols come from KiCad's own libraries or from hw/lib/rev_a.kicad_sym and are embedded in each
sheet, as KiCad does. Every pin of every placed unit must be either connected or listed as
unconnected: a pin forgotten in Python is an error here, not a silent open circuit.

  from kisch import Board
  b = Board("rev_a_a", "Rev A board A", outdir)
  s = b.sheet("power", "Analogue rails")
  s.part("Regulator_Linear:TPS7A20xxxDQN", "U1", "TPS7A2033PDQNR", fp, {"IN": "5V5_PRE", ...})
  s.r("R1", "10k", "NET_A", "GND")
  b.write()
  b.erc()
"""
import json
import math
import os
import pathlib
import re
import subprocess
import uuid

ROOT = pathlib.Path(__file__).resolve().parents[2]
HW = ROOT / "hw"
KICAD = pathlib.Path(os.environ.get(
    "KICAD10_DIR", pathlib.Path(os.environ.get("LOCALAPPDATA", "")) / "Programs/KiCad/10.0"))
STOCK_SYMBOLS = KICAD / "share/kicad/symbols"
STOCK_FOOTPRINTS = KICAD / "share/kicad/footprints"
KICAD_CLI = KICAD / "bin/kicad-cli.exe"
LOCAL_LIBS = {"rev_a": HW / "lib/rev_a.kicad_sym"}

GRID = 2.54
STUB = 2.54
CHAR_MM = 1.1  # Approximate width of one character of a 1.27 mm label, for spacing only.
NS = uuid.UUID("6b1d6f0e-4c1e-4b8e-9a51-0d5f3b3c7a10")


# ---------------------------------------------------------------- S-expressions

class Sym(str):
    """An unquoted atom."""


def parse(text):
    tokens = re.findall(r'\(|\)|"(?:[^"\\]|\\.)*"|[^\s()"]+', text)
    stack = [[]]
    for t in tokens:
        if t == "(":
            stack.append([])
        elif t == ")":
            done = stack.pop()
            stack[-1].append(done)
        elif t.startswith('"'):
            stack[-1].append(t[1:-1].replace('\\"', '"').replace("\\\\", "\\"))
        else:
            stack[-1].append(Sym(t))
    return stack[0][0]


def q(s):
    return '"' + str(s).replace("\\", "\\\\").replace('"', '\\"') + '"'


def dump(node, indent=0):
    if not isinstance(node, list):
        if isinstance(node, Sym):
            return str(node)
        if isinstance(node, (int, float)):
            return fmt(node)
        return q(node)
    pad = "\t" * indent
    if all(not isinstance(x, list) for x in node):
        return "(" + " ".join(dump(x) for x in node) + ")"
    head = []
    rest = node
    while rest and not isinstance(rest[0], list):
        head.append(dump(rest[0]))
        rest = rest[1:]
    inner = "\n".join(pad + "\t" + dump(x, indent + 1) for x in rest)
    return "(" + " ".join(head) + "\n" + inner + "\n" + pad + ")"


def fmt(v):
    if isinstance(v, float):
        s = f"{v:.4f}".rstrip("0").rstrip(".")
        return "0" if s in ("-0", "") else s
    return str(v)


def find(node, key):
    return [x for x in node if isinstance(x, list) and x and x[0] == key]


def find1(node, key):
    r = find(node, key)
    return r[0] if r else None


def S(*items):
    """Builds a node: S("at", 1, 2) -> [Sym("at"), 1, 2]."""
    return [Sym(items[0])] + list(items[1:])


def yes(flag):
    return Sym("yes" if flag else "no")


# ---------------------------------------------------------------- symbol libraries

_lib_cache = {}


def _lib(nick):
    if nick not in _lib_cache:
        path = LOCAL_LIBS.get(nick, STOCK_SYMBOLS / f"{nick}.kicad_sym")
        if not path.exists():
            raise FileNotFoundError(f"symbol library {nick}: {path}")
        tree = parse(path.read_text(encoding="utf-8"))
        _lib_cache[nick] = {x[1]: x for x in find(tree, "symbol")}
    return _lib_cache[nick]


def _flatten(nick, name):
    """The symbol with any `extends` resolved, its units renamed after it, as KiCad embeds it."""
    lib = _lib(nick)
    if name not in lib:
        raise KeyError(f"no symbol {name} in {nick}")
    sym = lib[name]
    parent_ref = find1(sym, "extends")
    if not parent_ref:
        out = [Sym("symbol"), f"{nick}:{name}"] + sym[2:]
        return out
    parent = _flatten(nick, parent_ref[1])
    pname = parent_ref[1]
    child_props = {p[1]: p for p in find(sym, "property")}
    out = [Sym("symbol"), f"{nick}:{name}"]
    for item in parent[2:]:
        if isinstance(item, list) and item and item[0] == "property" and item[1] in child_props:
            out.append(child_props.pop(item[1]))
        elif isinstance(item, list) and item and item[0] == "symbol":
            unit = list(item)
            unit[1] = name + unit[1][len(pname):]
            out.append(unit)
        else:
            out.append(item)
    for p in child_props.values():
        out.insert(2, p)
    return out


class Pin:
    def __init__(self, number, name, etype, x, y, angle, unit, hidden):
        self.number, self.name, self.etype = number, name, etype
        self.x, self.y, self.angle, self.unit, self.hidden = x, y, angle, unit, hidden

    def outward(self):
        """Unit vector, in schematic coordinates (y down), pointing away from the body."""
        return {0: (-1, 0), 180: (1, 0), 90: (0, 1), 270: (0, -1)}[int(self.angle) % 360]


class SymbolDef:
    def __init__(self, lib_id):
        self.lib_id = lib_id
        nick, name = lib_id.split(":", 1)
        self.node = _flatten(nick, name)
        self.name = name
        self.pins = []
        self.units = set()
        xs, ys = [0.0], [0.0]
        for unit in find(self.node, "symbol"):
            m = re.match(r".*_(\d+)_(\d+)$", unit[1])
            u, style = int(m.group(1)), int(m.group(2))
            if style > 1:
                continue
            if u:
                self.units.add(u)
            for g in unit:
                if not isinstance(g, list):
                    continue
                if g[0] == "pin":
                    at = find1(g, "at")
                    hidden = Sym("hide") in g or (find1(g, "hide") or [None, "no"])[1] == "yes"
                    self.pins.append(Pin(find1(g, "number")[1], find1(g, "name")[1], str(g[1]),
                                         float(at[1]), float(at[2]),
                                         float(at[3]) if len(at) > 3 else 0.0, u, hidden))
                for pt in find(g, "start") + find(g, "end") + [
                        p for pts in find(g, "pts") for p in find(pts, "xy")]:
                    xs.append(float(pt[1]))
                    ys.append(float(pt[2]))
        if not self.units:
            self.units = {1}
        self.body = (min(xs), max(xs), min(ys), max(ys))  # Library coordinates, y up.
        self.is_power = find1(self.node, "power") is not None

    def unit_pins(self, unit):
        return [p for p in self.pins if p.unit in (0, unit)]


_symdefs = {}


def symdef(lib_id):
    if lib_id not in _symdefs:
        _symdefs[lib_id] = SymbolDef(lib_id)
    return _symdefs[lib_id]


def footprint_exists(fp):
    if not fp:
        return False
    nick, name = fp.split(":", 1)
    local = HW / "lib" / f"{nick}.pretty" / f"{name}.kicad_mod"
    return local.exists() or (STOCK_FOOTPRINTS / f"{nick}.pretty" / f"{name}.kicad_mod").exists()


# ---------------------------------------------------------------- the model

class PartUnit:
    def __init__(self, sheet, lib_id, ref, value, footprint, conns, unit, fields, dnp, nc):
        self.sheet, self.lib_id, self.ref, self.value = sheet, lib_id, ref, value
        self.footprint, self.unit, self.fields, self.dnp = footprint, unit, fields, dnp
        self.sd = symdef(lib_id)
        pins = self.sd.unit_pins(unit)
        by_number = {p.number: p for p in pins}
        names = {}
        for p in pins:
            names.setdefault(p.name, []).append(p)
        self.net_of = {}
        for key, net in conns.items():
            key = str(key)
            if key in by_number:
                targets = [by_number[key]]
            elif key in names:
                targets = names[key]  # A name used on several pins (GND, NC) means all of them.
            else:
                raise KeyError(f"{ref} ({lib_id} unit {unit}): no pin {key!r}; pins are "
                               + ", ".join(f"{p.number}={p.name}" for p in pins))
            for t in targets:
                self.net_of[t.number] = net
        nc = set(str(n) for n in (nc or []))
        for key in list(nc):
            if key in names and key not in by_number:
                nc.discard(key)
                nc.update(p.number for p in names[key])
        missing = [f"{p.number}={p.name}" for p in pins if p.number not in self.net_of
                   and p.number not in nc]
        if missing:
            raise ValueError(f"{ref} unit {unit} on sheet {sheet.name}: pins neither connected "
                             f"nor marked unconnected: {', '.join(missing)}")
        both = nc & set(self.net_of)
        if both:
            raise ValueError(f"{ref}: pins both connected and unconnected: {sorted(both)}")
        self.nc = nc
        self.pins = pins


class Sheet:
    def __init__(self, board, name, title):
        self.board, self.name, self.title = board, name, title
        self.units = []
        self.flags = []
        self.notes = []

    def part(self, lib_id, ref, value, footprint, pins, unit=1, fields=None, dnp=False, nc=None):
        """pins: {pin number or name: net}. nc: pin numbers or names left unconnected."""
        pu = PartUnit(self, lib_id, ref, value, footprint, pins, unit, fields or {}, dnp, nc)
        self.units.append(pu)
        self.board._register(pu)
        return pu

    def two(self, lib_id, ref, value, footprint, a, b, fields=None, dnp=False):
        return self.part(lib_id, ref, value, footprint, {"1": a, "2": b}, fields=fields, dnp=dnp)

    def r(self, ref, value, a, b, fp="Resistor_SMD:R_0603_1608Metric", **kw):
        return self.two("Device:R", ref, value, fp, a, b, **kw)

    def c(self, ref, value, a, b, fp="Capacitor_SMD:C_0603_1608Metric", **kw):
        return self.two("Device:C", ref, value, fp, a, b, **kw)

    def cp(self, ref, value, plus, minus, fp, **kw):
        return self.two("Device:C_Polarized", ref, value, fp, plus, minus, **kw)

    def l(self, ref, value, a, b, fp, **kw):
        return self.two("Device:L", ref, value, fp, a, b, **kw)

    def fb(self, ref, value, a, b, fp="Inductor_SMD:L_0603_1608Metric", **kw):
        return self.two("Device:FerriteBead_Small", ref, value, fp, a, b, **kw)

    def row(self):
        """Starts a new row of parts on the drawing (groups a block visually)."""
        self.units.append(None)

    def flag(self, net):
        """A PWR_FLAG: tells ERC this net is driven (it arrives through a connector)."""
        self.flags.append(net)

    def note(self, text):
        self.notes.append(text)


class Board:
    def __init__(self, name, title, outdir, rev="A", company="stm32h7-audio-interface-dsp",
                 date="2026-11-19"):
        self.name, self.title, self.outdir = name, title, pathlib.Path(outdir)
        self.rev, self.company, self.date = rev, company, date
        self.sheets = []
        self.parts = {}  # ref -> list of PartUnit
        self.rails = {"GND": "power:GND", "CHASSIS": "power:Earth_Protective"}

    def rail(self, net, lib_id=None):
        """Draws this net with power symbols. Default shape: VEE for names starting with '-'."""
        self.rails[net] = lib_id or ("power:VEE" if net.startswith("-") else "power:VCC")

    def sheet(self, name, title):
        s = Sheet(self, name, title)
        self.sheets.append(s)
        return s

    def _register(self, pu):
        units = self.parts.setdefault(pu.ref, [])
        for other in units:
            if other.unit == pu.unit:
                raise ValueError(f"{pu.ref} unit {pu.unit} placed twice")
            if (other.lib_id, other.value, other.footprint) != (pu.lib_id, pu.value, pu.footprint):
                raise ValueError(f"{pu.ref}: units disagree on symbol, value or footprint")
        units.append(pu)

    # -- checks before drawing

    def nets(self):
        out = {}
        for s in self.sheets:
            for pu in s.units:
                if pu is None:
                    continue
                for num, net in pu.net_of.items():
                    out.setdefault(net, []).append((pu.ref, num, s.name))
            for net in s.flags:
                out.setdefault(net, [])
        return out

    def check(self):
        problems = []
        for ref, units in self.parts.items():
            sd = units[0].sd
            placed = {u.unit for u in units}
            if placed != sd.units:
                problems.append(f"{ref}: units placed {sorted(placed)} of {sorted(sd.units)}")
            fp = units[0].footprint
            if not footprint_exists(fp):
                problems.append(f"{ref}: footprint not found: {fp!r}")
        for net, pins in self.nets().items():
            if len(pins) == 1 and net not in self.rails:
                problems.append(f"net {net} has one pin only: {pins[0]}")
        return problems

    # -- drawing

    def uid(self, *parts):
        return str(uuid.uuid5(NS, "/".join([self.name] + [str(p) for p in parts])))

    def write(self):
        problems = self.check()
        if problems:
            raise ValueError("board " + self.name + ":\n  " + "\n  ".join(problems))
        self.outdir.mkdir(parents=True, exist_ok=True)
        root_uuid = self.uid("root")
        sheet_nets = {}
        for s in self.sheets:
            names = set()
            for pu in s.units:
                if pu is not None:
                    names.update(pu.net_of.values())
            names.update(s.flags)
            sheet_nets[s.name] = names
        global_nets = {n for n in self.nets()
                       if sum(n in v for v in sheet_nets.values()) > 1 and n not in self.rails}
        for page, s in enumerate(self.sheets, start=2):
            path = f"/{root_uuid}/{self.uid('sheet', s.name)}"
            text = _SheetWriter(self, s, path, global_nets).render()
            (self.outdir / f"{s.name}.kicad_sch").write_text(text, encoding="utf-8")
        (self.outdir / f"{self.name}.kicad_sch").write_text(self._root(root_uuid),
                                                            encoding="utf-8")
        self._project_files()

    def _root(self, root_uuid):
        body = [Sym("kicad_sch"), S("version", Sym("20250610")), S("generator", "kisch"),
                S("generator_version", "10.0"), S("uuid", root_uuid), S("paper", "A4"),
                self._title_block(self.title)]
        body.append(S("lib_symbols"))
        for i, s in enumerate(self.sheets):
            x = 25.4 + (i % 4) * 63.5
            y = 38.1 + (i // 4) * 38.1
            su = self.uid("sheet", s.name)
            body.append(S("sheet", S("at", x, y), S("size", 50.8, 20.32),
                          S("exclude_from_sim", Sym("no")), S("in_bom", Sym("yes")),
                          S("on_board", Sym("yes")), S("dnp", Sym("no")),
                          S("stroke", S("width", 0.1524), S("type", Sym("solid"))),
                          S("fill", S("color", 0, 0, 0, 0.0)), S("uuid", su),
                          S("property", "Sheetname", s.title, S("at", x, y - 0.7, 0),
                            _font(justify="left bottom")),
                          S("property", "Sheetfile", f"{s.name}.kicad_sch",
                            S("at", x, y + 21.0, 0), _font(justify="left top")),
                          S("instances", S("project", self.name,
                                           S("path", f"/{root_uuid}", S("page", str(i + 2)))))))
        body.append(S("sheet_instances", S("path", "/", S("page", "1"))))
        body.append(S("embedded_fonts", Sym("no")))
        return dump(body) + "\n"

    def _title_block(self, title):
        return S("title_block", S("title", title), S("date", self.date), S("rev", self.rev),
                 S("company", self.company))

    def _project_files(self):
        pro = {"meta": {"filename": f"{self.name}.kicad_pro", "version": 3},
               "sheets": [[self.uid("root"), "Root"]] + [
                   [self.uid("sheet", s.name), s.title] for s in self.sheets],
               "erc": {"rule_severities": {"lib_symbol_mismatch": "ignore",
                                           "lib_symbol_issues": "warning",
                                           "footprint_link_issues": "warning"}}}
        (self.outdir / f"{self.name}.kicad_pro").write_text(json.dumps(pro, indent=2) + "\n",
                                                           encoding="utf-8")
        rows = []
        for nick, path in LOCAL_LIBS.items():
            rel = os.path.relpath(path, self.outdir).replace("\\", "/")
            rows.append(f'  (lib (name "{nick}")(type "KiCad")(uri "${{KIPRJMOD}}/{rel}")'
                        '(options "")(descr "Rev A parts not in the KiCad libraries"))\n')
        (self.outdir / "sym-lib-table").write_text(
            "(sym_lib_table\n  (version 7)\n" + "".join(rows) + ")\n", encoding="utf-8")

    # -- checks after drawing

    def erc(self):
        """Runs KiCad's ERC; returns the list of violations (errors and warnings)."""
        out = self.outdir / f"{self.name}.erc.json"
        subprocess.run([str(KICAD_CLI), "sch", "erc", "--format", "json", "--severity-all",
                        "-o", str(out), str(self.outdir / f"{self.name}.kicad_sch")],
                       check=True, capture_output=True)
        report = json.loads(out.read_text(encoding="utf-8"))
        found = []
        for sheet in report.get("sheets", []):
            for v in sheet.get("violations", []):
                items = "; ".join(i.get("description", "") for i in v.get("items", []))
                found.append(f"{v['severity']}: {sheet.get('path')}: {v['type']}: "
                             f"{v['description']} [{items}]")
        return found

    def netlist(self):
        """Exports KiCad's netlist and returns {net name: {(ref, pin), ...}}."""
        out = self.outdir / f"{self.name}.net"
        subprocess.run([str(KICAD_CLI), "sch", "export", "netlist", "-o", str(out),
                        str(self.outdir / f"{self.name}.kicad_sch")],
                       check=True, capture_output=True)
        tree = parse(out.read_text(encoding="utf-8"))
        nets = {}
        for net in find(find1(tree, "nets"), "net"):
            name = find1(net, "name")[1].lstrip("/")
            nets[name] = {(find1(n, "ref")[1], find1(n, "pin")[1]) for n in find(net, "node")}
        return nets


def _font(justify=None, hide=False, size=1.27):
    eff = S("effects", S("font", S("size", size, size)))
    if justify:
        eff.append(S("justify", *[Sym(j) for j in justify.split()]))
    if hide:
        eff.append(S("hide", Sym("yes")))
    return eff


def _snap(v):
    return round(v / GRID) * GRID


class _SheetWriter:
    def __init__(self, board, sheet, path, global_nets):
        self.b, self.s, self.path, self.global_nets = board, sheet, path, global_nets
        self.items = []
        self.lib_ids = []
        self.n = 0

    def uid(self, *parts):
        self.n += 1
        return self.b.uid(self.s.name, self.n, *parts)

    def label_len(self, net):
        return len(net) * CHAR_MM + (4.0 if net in self.global_nets else 1.0)

    def extents(self, pu):
        """Room each side of the unit's origin, schematic coordinates: (left, right, up, down)."""
        x0, x1, y0, y1 = pu.sd.body
        left, right, up, down = -x0 + 1.27, x1 + 1.27, y1 + 3.0, -y0 + 3.0
        if all(p.outward()[0] == 0 for p in pu.pins):
            right = x1 + 2.0 + CHAR_MM * max(len(pu.ref), len(pu.value))
        for p in pu.pins:
            net = pu.net_of.get(p.number)
            reach = STUB + (self.label_len(net) if net and net not in self.b.rails else 6.0)
            if net is None:
                reach = 1.0
            dx, dy = p.outward()
            px, py = p.x, -p.y
            if dx < 0:
                left = max(left, -px + reach)
            elif dx > 0:
                right = max(right, px + reach)
            elif dy < 0:
                up = max(up, -py + reach)
            else:
                down = max(down, py + reach)
        return left, right, up, down

    def layout(self):
        """Shelf packing in reading order; returns the page size used."""
        boxes = [(pu, self.extents(pu)) if pu is not None else (None, None)
                 for pu in self.s.units]
        boxes += [(("flag", net), (2.54, 10.0, 8.0, 3.0)) for net in self.s.flags]
        for paper, (w, h) in (("A3", (420, 297)), ("A2", (594, 420)), ("A1", (841, 594)),
                              ("A0", (1189, 841))):
            x, y, row_h = 15.0, 25.0, 0.0
            placed = []
            ok = True
            for item, ext in boxes:
                if item is None:
                    if x > 15.0:
                        x, y, row_h = 15.0, y + row_h + 10.16, 0.0
                    continue
                l, r, u, d = ext
                if x + l + r > w - 15:
                    x, y, row_h = 15.0, y + row_h + 5.08, 0.0
                ox, oy = _snap(x + l), _snap(y + u)
                placed.append((item, ox, oy))
                x = ox + r + 5.08
                row_h = max(row_h, (oy - y) + d)
                if y + row_h > h - 40:
                    ok = False
                    break
            if ok:
                return paper, placed
        raise ValueError(f"sheet {self.s.name} does not fit A0")

    def render(self):
        paper, placed = self.layout()
        sheet_uuid = self.path.rsplit("/", 1)[1]
        for item, ox, oy in placed:
            if isinstance(item, tuple):
                self.power(item[1], ox, oy, "power:PWR_FLAG", 0, flag=True)
                self.wire(ox, oy, ox + 5.08, oy)
                self.place_net(item[1], ox + 5.08, oy, (1, 0))
            else:
                self.unit(item, ox, oy)
        for t, (x, y) in zip(self.s.notes, [(15, 15 + 4 * i) for i in range(len(self.s.notes))]):
            self.items.append(S("text", t, S("exclude_from_sim", Sym("no")), S("at", x, y, 0),
                                _font(justify="left bottom"), S("uuid", self.uid("note"))))
        lib = []
        seen = set()
        for lib_id in self.lib_ids:
            if lib_id not in seen:
                seen.add(lib_id)
                lib.append(symdef(lib_id).node)
        body = [Sym("kicad_sch"), S("version", Sym("20250610")), S("generator", "kisch"),
                S("generator_version", "10.0"), S("uuid", sheet_uuid), S("paper", paper),
                self.b._title_block(f"{self.b.title}: {self.s.title}"),
                [Sym("lib_symbols")] + lib] + self.items + [S("embedded_fonts", Sym("no"))]
        return dump(body) + "\n"

    def wire(self, x1, y1, x2, y2):
        self.items.append(S("wire", S("pts", S("xy", x1, y1), S("xy", x2, y2)),
                            S("stroke", S("width", 0), S("type", Sym("default"))),
                            S("uuid", self.uid("w"))))

    def place_net(self, net, x, y, d):
        if net in self.b.rails:
            self.power(net, x, y, self.b.rails[net], d)
            return
        ang = {(1, 0): 0, (-1, 0): 180, (0, -1): 90, (0, 1): 270}[d]
        just = {0: "left bottom", 180: "right bottom", 90: "left bottom", 270: "right bottom"}[ang]
        if net in self.global_nets:
            gjust = {0: "left", 180: "right", 90: "left", 270: "right"}[ang]
            self.items.append(S("global_label", net, S("shape", Sym("bidirectional")),
                                S("at", x, y, ang), S("fields_autoplaced", Sym("yes")),
                                _font(justify=gjust), S("uuid", self.uid("g", net)),
                                S("property", "Intersheetrefs", "${INTERSHEET_REFS}",
                                  S("at", x, y, 0), _font(hide=True))))
        else:
            self.items.append(S("label", net, S("at", x, y, ang), S("fields_autoplaced",
                                Sym("yes")), _font(justify=just), S("uuid", self.uid("l", net))))

    def power(self, net, x, y, lib_id, d, flag=False):
        self.lib_ids.append(lib_id)
        sd = symdef(lib_id)
        # Power symbols have their pin at the origin, so rotation only turns the graphic.
        down = lib_id in ("power:GND", "power:VEE", "power:Earth_Protective")
        rot = {(1, 0): 270, (-1, 0): 90, (0, -1): 0, (0, 1): 180}.get(d, 0) if not flag else 0
        if down:
            rot = (rot + 180) % 360
        ref = "#FLG" if flag else "#PWR"
        self.b._pwr = getattr(self.b, "_pwr", 0) + 1
        refn = f"{ref}{self.b._pwr:03d}"
        u = self.uid("p", net)
        node = S("symbol", S("lib_id", lib_id), S("at", x, y, rot), S("unit", 1),
                 S("exclude_from_sim", Sym("no")), S("in_bom", Sym("no")),
                 S("on_board", Sym("yes")), S("dnp", Sym("no")), S("uuid", u),
                 S("property", "Reference", refn, S("at", x, y, 0), _font(hide=True)),
                 S("property", "Value", "PWR_FLAG" if flag else net, S("at", x, y - 3.2, 0),
                   _font(hide=False)),
                 S("property", "Footprint", "", S("at", x, y, 0), _font(hide=True)),
                 S("property", "Datasheet", "", S("at", x, y, 0), _font(hide=True)))
        for p in sd.pins:
            node.append(S("pin", p.number, S("uuid", self.uid("pp", net))))
        node.append(S("instances", S("project", self.b.name,
                                     S("path", self.path, S("reference", refn), S("unit", 1)))))
        self.items.append(node)

    def unit(self, pu, ox, oy):
        self.lib_ids.append(pu.lib_id)
        x0, x1, y0, y1 = pu.sd.body
        u = self.b.uid("unit", pu.ref, pu.unit)
        if all(pp.outward()[0] == 0 for pp in pu.pins):  # Vertical part: text to the right.
            props = [("Reference", pu.ref, ox + x1 + 1.5, oy - 0.6, False),
                     ("Value", pu.value, ox + x1 + 1.5, oy + 1.9, False)]
            just = "left"
        else:
            props = [("Reference", pu.ref, ox, oy - y1 - 1.5, False),
                     ("Value", pu.value, ox, oy - y0 + 1.5, False)]
            just = None
        props += [
                 ("Footprint", pu.footprint, ox, oy, True),
                 ("Footprint", pu.footprint, ox, oy, True),
                 ("Datasheet", "", ox, oy, True)]
        props += [(k, v, ox, oy, True) for k, v in pu.fields.items()]
        node = S("symbol", S("lib_id", pu.lib_id), S("at", ox, oy, 0), S("unit", pu.unit),
                 S("exclude_from_sim", Sym("no")), S("in_bom", yes(True)),
                 S("on_board", Sym("yes")), S("dnp", yes(pu.dnp)), S("uuid", u))
        for i, (k, v, x, y, hide) in enumerate(props):
            node.append(S("property", k, v, S("at", x, y, 0),
                          _font(hide=hide, justify=just if i < 2 else None)))
        for p in pu.pins:
            node.append(S("pin", p.number, S("uuid", self.b.uid("pin", pu.ref, pu.unit,
                                                               p.number))))
        node.append(S("instances", S("project", self.b.name,
                                     S("path", self.path, S("reference", pu.ref),
                                       S("unit", pu.unit)))))
        self.items.append(node)
        for p in pu.pins:
            px, py = ox + p.x, oy - p.y
            if p.number in pu.nc:
                self.items.append(S("no_connect", S("at", px, py), S("uuid", self.uid("nc"))))
                continue
            dx, dy = p.outward()
            ex, ey = px + dx * STUB, py + dy * STUB
            self.wire(px, py, ex, ey)
            self.place_net(pu.net_of[p.number], ex, ey, (dx, dy))
