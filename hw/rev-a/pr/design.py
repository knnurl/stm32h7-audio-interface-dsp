"""Rev A panel right (PR): the netlist that kisch.py draws as hw/rev-a/pr/.

    python hw/rev-a/pr/design.py

POT1 bass, POT2 mid, POT3 treble, POT4 monitor, POT5 phones, BTN4 mute, BTN5 dim, LED5 and LED6,
the NJ6FD-V phones jack with its TVS, J_PJ from PL and J_HP from board A
(rev_a_board_split.md sections 1 and 3). The headphone nets never meet GND on this board
(rev_a_architecture.md section 7). The circuit, values and open points: NOTES.md.
"""
import pathlib
import sys

HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parents[1] / "tools"))
from kisch import Board  # noqa: E402
import links  # noqa: E402

HAND = {"Fit": "hand"}
IDC = "Connector_IDC:IDC-Header_{}_P2.54mm_Vertical"
POT_FP = "Potentiometer_THT:Potentiometer_Alps_RK09L_Single_Vertical"
BTN_FP = "Button_Switch_THT:SW_SPST_Omron_B3F-50xx"
LED_FP = "LED_THT:LED_D3.0mm"
HOLE_FP = "MountingHole:MountingHole_3.2mm_M3"

# 2.5 mA from PANEL_3V3 with an amber LED at about 2.0 V: (3.3 - 2.0) / 2.5 mA = 520 ohm, E24 510.
LED_R = "510"
LED_COLOUR = "amber"


def build():
    b = Board("rev_a_pr", "Rev A panel right", HERE)
    b.rail("PANEL_3V3")

    s = b.sheet("cables", "Cables and mounting")
    pins, nc = links.pins("J_PJ")
    s.part("Connector_Generic:Conn_02x08_Odd_Even", "J1", "J_PJ", IDC.format("2x08"), pins,
           nc=nc, fields=HAND)
    pins, nc = links.pins("J_HP")
    s.part("Connector_Generic:Conn_02x03_Odd_Even", "J2", "J_HP", IDC.format("2x03"), pins,
           nc=nc, fields=HAND)
    s.row()
    for ref in ("H1", "H2"):
        s.part("Mechanical:MountingHole", ref, "MountingHole", HOLE_FP, {})
    s.row()
    # GND and PANEL_3V3 arrive only through J_PJ.
    s.flag("GND")
    s.flag("PANEL_3V3")
    s.note("PR: ground only through J_PJ. POT_GND is not joined to GND here. HP_L, HP_R, "
           "HP_L_RET, HP_R_RET never touch GND. Mounting holes unplated, not bonded.")

    s = b.sheet("pots", "Pots")
    s.note("Pot between POT_REF (CW end, pin 3) and POT_GND (pin 1); 10 nF wiper to POT_GND at "
           "the pot. Series R and 100 nF are on board D.")
    for n, use, mpn in ((1, "bass", "Alps RK09L, centre detent [Verify part number]"),
                        (2, "mid", "Alps RK09L, centre detent [Verify part number]"),
                        (3, "treble", "Alps RK09L, centre detent [Verify part number]"),
                        (4, "monitor volume", "Alps RK09L1140A5L [Verify]"),
                        (5, "phones volume", "Alps RK09L1140A5L [Verify]")):
        value = "10k lin detent" if n <= 3 else "10k lin"
        s.part("Device:R_Potentiometer", f"RV{n}", value, POT_FP,
               {"3": "POT_REF", "2": f"POT{n}", "1": "POT_GND"},
               fields={**HAND, "Use": use, "MPN": mpn})
        s.c(f"C{n}", "10n", f"POT{n}", "POT_GND")
        s.row()

    s = b.sheet("controls", "Buttons and LEDs")
    s.note("Buttons to GND; pull-ups and filters on board D. LED anode from PANEL_3V3 through "
           "510 ohm, the MCU sinks the cathode line.")
    for n, use in ((4, "mute"), (5, "dim")):
        s.part("Switch:SW_Push", f"SW{n}", "B3F-5000", BTN_FP, {"1": f"BTN{n}", "2": "GND"},
               fields={**HAND, "Use": use})
    s.row()
    for n, use in ((5, "mute"), (6, "dim")):
        s.r(f"R{n}", LED_R, "PANEL_3V3", f"LED{n}_A")
        s.part("Device:LED", f"D{n}", f"LED {LED_COLOUR} 3mm", LED_FP,
               {"A": f"LED{n}_A", "K": f"LED{n}"}, fields={**HAND, "Use": use})
        s.row()

    s = b.sheet("phones", "Phones jack")
    s.note("Tip HP_L, ring HP_R, sleeve HP_L_RET. HP_R_RET joins the sleeve only through NT1, "
           "at the jack. TVS from tip and ring to the sleeve, at the jack. Switch contacts open.")
    s.part("Connector_Audio:NJ6FD-V", "J3", "NJ6FD-V",
           "Connector_Audio:Jack_6.35mm_Neutrik_NJ6FD-V_Vertical",
           {"T": "HP_L", "R": "HP_R", "S": "HP_L_RET"}, nc=["TN", "RN", "SN"],
           fields={**HAND, "Use": "phones"})
    s.part("Device:NetTie_2", "NT1", "NetTie_2", "NetTie:NetTie-2_SMD_Pad0.5mm",
           {"1": "HP_L_RET", "2": "HP_R_RET"})
    s.row()
    for ref, net in (("D8", "HP_L"), ("D9", "HP_R")):
        s.part("Device:D_TVS", ref, "PESD12VL1BA", "Diode_SMD:D_SOD-323",
               {"A1": net, "A2": "HP_L_RET"},
               fields={"MPN": "Nexperia PESD12VL1BA,115", "LCSC": "C38558 [Verify]"})
    return b


def main():
    b = build()
    b.write()
    found = b.erc()
    for v in found:
        print(v)
    errors = [v for v in found if v.startswith("error")]
    print(f"ERC {b.name}: {len(errors)} errors, {len(found) - len(errors)} warnings")
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
