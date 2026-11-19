"""Writes hw/lib/rev_a.kicad_sym: the rev A parts that KiCad's libraries lack.

    python hw/tools/make_lib.py

Pin numbers come from the datasheets named in each entry. An entry whose numbers could not be
read from a datasheet says so in its description ("PIN NUMBERS UNVERIFIED"); the schematic
review lists those, and they are checked before layout.
"""
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from kisch import HW, S, Sym, dump  # noqa: E402

P = 2.54

# (number, name, type, side): side L, R, T (top) or B (bottom). Types as KiCad's: input, output,
# bidirectional, passive, power_in, power_out, no_connect.
PCM3168A = {
    "name": "PCM3168A", "ref": "U",
    "fp": "Package_QFP:Texas_TQFP-64-1EP_10x10mm_P0.5mm_EP8x8mm_Mask5x5mm_ThermalVias",
    "ds": "https://www.ti.com/lit/ds/symlink/pcm3168a.pdf",
    "desc": "24-bit 6-in 8-out audio codec, HTQFP-64 PowerPAD (pins from SBAS452A, Pin "
            "Functions). Footprint to be matched to the PAP0064 land pattern in stage 4",
    "pins": [
        ("4", "~{RST}", "input", "L"), ("5", "OVF", "output", "L"), ("48", "MODE", "input", "L"),
        ("42", "MC/SCL/FMT", "input", "L"), ("43", "MDI/SDA/DEMP", "bidirectional", "L"),
        ("44", "MDO/ADR1/MD1", "bidirectional", "L"), ("45", "MS/ADR0/MD0", "input", "L"),
        ("41", "SCKI", "input", "L"), ("6", "LRCKAD", "bidirectional", "L"),
        ("7", "BCKAD", "bidirectional", "L"), ("35", "LRCKDA", "bidirectional", "L"),
        ("36", "BCKDA", "bidirectional", "L"), ("37", "DIN1", "input", "L"),
        ("38", "DIN2", "input", "L"), ("39", "DIN3", "input", "L"), ("40", "DIN4", "input", "L"),
        ("8", "DOUT1", "output", "L"), ("9", "DOUT2", "output", "L"),
        ("10", "DOUT3", "output", "L"), ("13", "ZERO", "output", "L"),
        ("52", "VIN1+", "input", "R"), ("51", "VIN1-", "input", "R"),
        ("54", "VIN2+", "input", "R"), ("53", "VIN2-", "input", "R"),
        ("56", "VIN3+", "input", "R"), ("55", "VIN3-", "input", "R"),
        ("58", "VIN4+", "input", "R"), ("57", "VIN4-", "input", "R"),
        ("62", "VIN5+", "input", "R"), ("61", "VIN5-", "input", "R"),
        ("64", "VIN6+", "input", "R"), ("63", "VIN6-", "input", "R"),
        ("59", "VREFAD1", "passive", "R"), ("60", "VREFAD2", "passive", "R"),
        ("1", "VCOMAD", "passive", "R"), ("15", "VCOMDA", "passive", "R"),
        ("31", "VOUT1+", "output", "R"), ("32", "VOUT1-", "output", "R"),
        ("29", "VOUT2+", "output", "R"), ("30", "VOUT2-", "output", "R"),
        ("27", "VOUT3+", "output", "R"), ("28", "VOUT3-", "output", "R"),
        ("25", "VOUT4+", "output", "R"), ("26", "VOUT4-", "output", "R"),
        ("23", "VOUT5+", "output", "R"), ("24", "VOUT5-", "output", "R"),
        ("21", "VOUT6+", "output", "R"), ("22", "VOUT6-", "output", "R"),
        ("19", "VOUT7+", "output", "R"), ("20", "VOUT7-", "output", "R"),
        ("17", "VOUT8+", "output", "R"), ("18", "VOUT8-", "output", "R"),
        ("49", "VCCAD1", "power_in", "T"), ("3", "VCCAD2", "power_in", "T"),
        ("14", "VCCDA1", "power_in", "T"), ("34", "VCCDA2", "power_in", "T"),
        ("46", "VDD1", "power_in", "T"), ("12", "VDD2", "power_in", "T"),
        ("50", "AGNDAD1", "power_in", "B"), ("2", "AGNDAD2", "power_in", "B"),
        ("16", "AGNDDA1", "power_in", "B"), ("33", "AGNDDA2", "power_in", "B"),
        ("47", "DGND1", "power_in", "B"), ("11", "DGND2", "power_in", "B"),
        ("65", "PAD", "passive", "B"),
    ],
}


def ldo(name, desc, ds):
    return {
        "name": name, "ref": "U",
        "fp": "Package_SO:HVSSOP-8-1EP_3x3mm_P0.65mm_EP1.57x1.89mm_ThermalVias",
        "ds": ds, "desc": desc,
        "pins": [("8", "IN", "power_in", "L"), ("5", "EN", "input", "L"),
                 ("6", "NR/SS", "passive", "L"), ("1", "OUT", "power_out", "R"),
                 ("2", "FB", "input", "R"), ("3", "NC", "no_connect", "R"),
                 ("7", "DNC", "no_connect", "R"), ("4", "GND", "power_in", "B"),
                 ("9", "PAD", "passive", "B")],
    }


TPS7A4901 = ldo("TPS7A4901", "36 V 150 mA low-noise positive LDO, adjustable, HVSSOP-8 PowerPAD "
                "(pins from SBVS121E; PowerPAD open or to GND)",
                "https://www.ti.com/lit/ds/symlink/tps7a49.pdf")
TPS7A3001 = ldo("TPS7A3001", "-36 V -200 mA low-noise negative LDO, adjustable, HVSSOP-8 "
                "PowerPAD (pins from SBVS125D; PowerPAD open or to GND). IN, OUT and FB are "
                "negative", "https://www.ti.com/lit/ds/symlink/tps7a30.pdf")

WRA1215S = {
    "name": "WRA1215S-3WR2", "ref": "PS",
    "fp": "Connector_PinHeader_2.54mm:PinHeader_1x08_P2.54mm_Vertical",
    "ds": "https://www.mornsun-power.com/html/products-detail/WRA_S-3WR2.html",
    "desc": "Isolated DC-DC 9-18 V in, +/-15 V 100 mA out, 3 W, SIP-8. PIN NUMBERS UNVERIFIED: "
            "the datasheet gives them only in a drawing; check against 'Dimensions and "
            "Recommended Layout' before layout. Footprint: a 1x8 2.54 mm placeholder "
            "until stage 4",
    "pins": [("2", "Vin", "power_in", "L"), ("3", "Ctrl", "input", "L"),
             ("1", "GND", "power_in", "L"), ("6", "+Vo", "power_out", "R"),
             ("7", "0V", "power_out", "R"), ("8", "-Vo", "power_out", "R")],
}

PLR135 = {
    "name": "PLR135", "ref": "U",
    "fp": "OptoDevice:Toshiba_TORX170_TORX173_TORX193_TORX194",
    "ds": "https://www.everlight.com",
    "desc": "Toslink optical receiver, 3.3 V. PIN NUMBERS UNVERIFIED (batch 10, footprint only)",
    "pins": [("3", "VCC", "power_in", "L"), ("2", "GND", "power_in", "L"),
             ("1", "VOUT", "output", "R")],
}

PLT133 = {
    "name": "PLT133", "ref": "U",
    "fp": "OptoDevice:Toshiba_TOTX170_TOTX173_TOTX193_TOTX194",
    "ds": "https://www.everlight.com",
    "desc": "Toslink optical transmitter, 3.3 V. PIN NUMBERS UNVERIFIED (batch 10, footprint "
            "only)",
    "pins": [("2", "VCC", "power_in", "L"), ("1", "GND", "power_in", "L"),
             ("3", "VIN", "input", "R")],
}

PARTS = [PCM3168A, TPS7A4901, TPS7A3001, WRA1215S, PLR135, PLT133]


def _prop(key, value, x, y, hide=False):
    eff = S("effects", S("font", S("size", 1.27, 1.27)))
    if hide:
        eff.append(S("hide", Sym("yes")))
    return S("property", key, value, S("at", x, y, 0), eff)


def build(part):
    pins = part["pins"]
    side = {s: [p for p in pins if p[3] == s] for s in "LRTB"}
    longest = max(len(p[1]) for p in pins)
    rows = max(len(side["L"]), len(side["R"]), 1)
    cols = max(len(side["T"]), len(side["B"]), 1)
    half_w = max(P * 4, (cols + 1) * P / 2, longest * 1.27 + P)
    half_w = round(half_w / P) * P
    half_h = round(((rows + 1) * P / 2) / P + 0.5) * P
    name = part["name"]
    body = S("symbol", f"{name}_0_1",
             S("rectangle", S("start", -half_w, half_h), S("end", half_w, -half_h),
               S("stroke", S("width", 0.254), S("type", Sym("default"))),
               S("fill", S("type", Sym("background")))))
    unit = [Sym("symbol"), f"{name}_1_1"]
    length = P * 2

    def add(p, x, y, ang):
        num, pname, etype, _ = p
        unit.append(S("pin", Sym(etype), Sym("line"), S("at", x, y, ang), S("length", length),
                      S("name", pname, S("effects", S("font", S("size", 1.27, 1.27)))),
                      S("number", num, S("effects", S("font", S("size", 1.27, 1.27))))))

    for i, p in enumerate(side["L"]):
        add(p, -half_w - length, half_h - P * (i + 1), 0)
    for i, p in enumerate(side["R"]):
        add(p, half_w + length, half_h - P * (i + 1), 180)
    start_t = -P * ((len(side["T"]) - 1) // 2)
    for i, p in enumerate(side["T"]):
        add(p, start_t + P * i, half_h + length, 270)
    start_b = -P * ((len(side["B"]) - 1) // 2)
    for i, p in enumerate(side["B"]):
        add(p, start_b + P * i, -half_h - length, 90)
    return S("symbol", name, S("pin_names", S("offset", 1.016)),
             S("exclude_from_sim", Sym("no")), S("in_bom", Sym("yes")),
             S("on_board", Sym("yes")),
             _prop("Reference", part["ref"], -half_w, half_h + 1.27),
             _prop("Value", name, -half_w, -half_h - 1.27),
             _prop("Footprint", part["fp"], 0, 0, True),
             _prop("Datasheet", part["ds"], 0, 0, True),
             _prop("Description", part["desc"], 0, 0, True),
             body, unit)


def main():
    lib = [Sym("kicad_symbol_lib"), S("version", Sym("20241209")), S("generator", "make_lib"),
           S("generator_version", "10.0")] + [build(p) for p in PARTS]
    out = HW / "lib/rev_a.kicad_sym"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(dump(lib) + "\n", encoding="utf-8")
    print(f"wrote {out} ({len(PARTS)} symbols)")


if __name__ == "__main__":
    main()
