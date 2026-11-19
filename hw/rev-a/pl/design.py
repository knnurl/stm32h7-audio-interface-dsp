"""Rev A panel left (PL): the netlist that kisch.py draws as hw/rev-a/pl/.

    python hw/rev-a/pl/design.py

LEDs 1 to 4 and 7, POT6 FX amount and POT7 blend, both encoders, BTN1 to BTN3, the OLED header,
J_PANEL from board D and J_PJ to PR (rev_a_board_split.md sections 1 and 3). Everything PR uses
passes straight through from J_PANEL to J_PJ. The circuit, values and open points: NOTES.md.
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
ENC_FP = "Rotary_Encoder:RotaryEncoder_Alps_EC11E-Switch_Vertical_H20mm"
BTN_FP = "Button_Switch_THT:SW_SPST_Omron_B3F-50xx"
LED_FP = "LED_THT:LED_D3.0mm"
HOLE_FP = "MountingHole:MountingHole_3.2mm_M3"

# 2.5 mA from PANEL_3V3 with an amber LED at about 2.0 V: (3.3 - 2.0) / 2.5 mA = 520 ohm in all.
# Board D has 150 ohm in each LED line at the MCU end (protection, architecture 9), so the
# panel's share is 520 - 150 = 370: E24 360 ohm, 510 ohm in all, 2.55 mA.
LED_R = "360"
LED_COLOUR = "amber"


def build():
    b = Board("rev_a_pl", "Rev A panel left", HERE)
    b.rail("PANEL_3V3")

    s = b.sheet("cables", "Cables and mounting")
    pins, nc = links.pins("J_PANEL")
    s.part("Connector_Generic:Conn_02x20_Odd_Even", "J1", "J_PANEL", IDC.format("2x20"), pins,
           nc=nc, fields=HAND)
    pins, nc = links.pins("J_PJ")
    s.part("Connector_Generic:Conn_02x08_Odd_Even", "J2", "J_PJ", IDC.format("2x08"), pins,
           nc=nc, fields=HAND)
    s.row()
    for ref in ("H1", "H2"):
        s.part("Mechanical:MountingHole", ref, "MountingHole", HOLE_FP, {})
    s.row()
    # GND and PANEL_3V3 arrive only through J_PANEL.
    s.flag("GND")
    s.flag("PANEL_3V3")
    s.note("PL: ground only through J_PANEL's ground conductors. POT_GND is not joined to GND "
           "here. Mounting holes unplated, not bonded.")

    s = b.sheet("leds", "LEDs")
    s.note("Anode from PANEL_3V3 through the resistor; the MCU sinks the cathode line "
           "(active low PWM). 360 ohm here plus 150 ohm on board D: about 2.5 mA at Vf 2.0 V.")
    for n, use in ((1, "input 1 signal"), (2, "input 1 clip"), (3, "input 2 signal"),
                   (4, "input 2 clip"), (7, "FX on")):
        s.r(f"R{n}", LED_R, "PANEL_3V3", f"LED{n}_A")
        s.part("Device:LED", f"D{n}", f"LED {LED_COLOUR} 3mm", LED_FP,
               {"A": f"LED{n}_A", "K": f"LED{n}"}, fields={**HAND, "Use": use})
        s.row()

    s = b.sheet("pots", "Pots")
    s.note("Pot between POT_REF (CW end, pin 3) and POT_GND (pin 1); 10 nF wiper to POT_GND at "
           "the pot. Series R and 100 nF are on board D.")
    for n, use in ((6, "FX amount"), (7, "blend")):
        s.part("Device:R_Potentiometer", f"RV{n}", "10k lin", POT_FP,
               {"3": "POT_REF", "2": f"POT{n}", "1": "POT_GND"},
               fields={**HAND, "Use": use, "MPN": "Alps RK09L1140A5L [Verify]"})
        s.c(f"C{n}", "10n", f"POT{n}", "POT_GND")
        s.row()

    s = b.sheet("controls", "Encoders and buttons")
    s.note("Switches to GND only; pull-ups, series R and filter capacitors are on board D.")
    for i, ref in ((1, "SW6"), (2, "SW7")):
        s.part("Device:RotaryEncoder_Switch", ref, "EC11E encoder with switch", ENC_FP,
               {"A": f"ENC{i}_A", "B": f"ENC{i}_B", "C": "GND", "S1": f"ENC{i}_SW",
                "S2": "GND"},
               fields={**HAND, "Use": ("select", "value")[i - 1]})
    s.row()
    for n, use in ((1, "FX select"), (2, "FX on"), (3, "tap")):
        s.part("Switch:SW_Push", f"SW{n}", "B3F-5000", BTN_FP, {"1": f"BTN{n}", "2": "GND"},
               fields={**HAND, "Use": use})

    s = b.sheet("oled", "OLED header")
    s.note("I2C4, PANEL_3V3 and GND only (architecture 11.5); pins 7 to 10 open. Pull-ups "
           "4.7 k are at the MCU end.")
    s.part("Connector_Generic:Conn_02x05_Odd_Even", "J3", "OLED", IDC.format("2x05"),
           {"1": "PANEL_3V3", "2": "GND", "3": "I2C4_SCL", "4": "GND", "5": "I2C4_SDA",
            "6": "GND"}, nc=["7", "8", "9", "10"], fields=HAND)
    s.row()
    s.c("C8", "100n", "PANEL_3V3", "GND")
    s.c("C9", "10u", "PANEL_3V3", "GND", fp="Capacitor_SMD:C_0805_2012Metric")
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
