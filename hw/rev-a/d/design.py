"""Rev A board D: power and digital, over the Nucleo-H755ZI-Q (batch 5, stage 3).

    python hw/rev-a/d/design.py

Writes the KiCad project into this folder, runs KiCad's ERC, prints every violation and exits
non-zero on any error. Values and their derivations: NOTES.md beside this file. Sources:
docs/notes/rev_a_board_split.md, rev_a_architecture.md, pin_plan.md, part_selection.md.
"""
import pathlib
import sys

HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parents[1] / "tools"))
from kisch import Board  # noqa: E402
import links  # noqa: E402

# Footprints used more than once.
R0603 = "Resistor_SMD:R_0603_1608Metric"
R0805 = "Resistor_SMD:R_0805_2012Metric"
R1206 = "Resistor_SMD:R_1206_3216Metric"
C0603 = "Capacitor_SMD:C_0603_1608Metric"
C1206 = "Capacitor_SMD:C_1206_3216Metric"
C1210 = "Capacitor_SMD:C_1210_3225Metric"
SOT23 = "Package_TO_SOT_SMD:SOT-23"
SOD123 = "Diode_SMD:D_SOD-123"
SJ_OPEN = "Jumper:SolderJumper-2_P1.3mm_Open_RoundedPad1.0x1.5mm"
TP_PAD = "TestPoint:TestPoint_Pad_D1.5mm"
TP_POST = "TestPoint:TestPoint_Keystone_5005-5009_Compact"
IDC_2X20 = "Connector_IDC:IDC-Header_2x20_P2.54mm_Vertical"
HAND = {"Fit": "hand"}

b = Board("rev_a_d", "Rev A board D: power and digital", HERE)
for rail in ("12V_P", "5V_DIG", "5V5_PRE", "+15V_RAW", "-15V_RAW", "NUCLEO_3V3"):
    b.rail(rail)


def sj(s, ref, a, bnet):
    """An open solder jumper: a regulator's output link, bridged by hand at bring-up."""
    return s.part("Jumper:SolderJumper_2_Open", ref, "SJ open", SJ_OPEN, {"A": a, "B": bnet})


# ------------------------------------------------------------------ 1. power entry
s = b.sheet("power_entry", "Power entry and protection")
s.note("J1 to the panel-mount DC jack (pins 1, 2) and the power switch (pins 3, 4). 12V_IN is "
       "after the switch. Cut-off values to be simulated before layout [Verify].")
s.part("Connector_Generic:Conn_01x04", "J1", "B4B-XH-A",
       "Connector_JST:JST_XH_B4B-XH-A_1x04_P2.50mm_Vertical",
       {"1": "12V_JACK", "2": "GND", "3": "12V_JACK", "4": "12V_IN"}, fields=HAND)
s.part("Device:Polyfuse", "F1", "PTC 1.1A hold 30V", "Fuse:Fuse_1812_4532Metric",
       {"1": "12V_IN", "2": "12V_F"})
s.row()
# Reverse polarity: Q1, drain to the input, so its body diode conducts only the right way.
s.part("Transistor_FET:DMP3099L", "Q1", "DMP3099L-7", SOT23,
       {"D": "12V_F", "S": "12V_RP", "G": "Q1_G"})
s.r("R1", "100k", "Q1_G", "GND")
s.part("Device:D_Zener", "D1", "BZT52C10", SOD123, {"K": "12V_RP", "A": "Q1_G"})
s.row()
# Over-voltage cut-off: Q2 back to back with Q1 (common source), turned off by Q3 when the
# TL431 sees 12V_RP above about 15.7 V. C1 with R2 soft-starts Q2 (inrush into C2).
s.part("Transistor_FET:DMP3099L", "Q2", "DMP3099L-7", SOT23,
       {"S": "12V_RP", "D": "12V_P", "G": "Q2_G"})
s.r("R2", "100k", "Q2_G", "GND")
s.part("Device:D_Zener", "D2", "BZT52C10", SOD123, {"K": "12V_RP", "A": "Q2_G"})
s.c("C1", "100n 25V", "Q2_G", "12V_RP")
s.r("R3", "53.6k 1%", "12V_RP", "OV_SENSE")
s.r("R4", "10k 1%", "OV_SENSE", "GND")
s.r("R5", "1M 1%", "Q2_G", "OV_SENSE")
s.part("Reference_Voltage:TL431DBZ", "U1", "TL431BIDBZR", SOT23,
       {"K": "OV_K", "REF": "OV_SENSE", "A": "GND"})
s.r("R6", "10k", "OV_K", "Q3_B", fp=R0805)
s.r("R7", "10k", "Q3_B", "12V_RP")
s.part("Transistor_BJT:MMBT3906", "Q3", "MMBT3906", SOT23,
       {"E": "12V_RP", "B": "Q3_B", "C": "Q2_G"})
s.row()
s.part("Device:D_Zener", "D3", "SMBJ15A", "Diode_SMD:D_SMB", {"K": "12V_P", "A": "GND"})
s.cp("C2", "1000u 25V", "12V_P", "GND", "Capacitor_SMD:CP_Elec_10x10.5", fields=HAND)
s.flag("12V_P")
# No PWR_FLAG on GND: PS1's 0V pin is a power output on GND, and a flag there is an ERC error.

# ------------------------------------------------------------------ 2. bucks
s = b.sheet("bucks", "Bucks: 5V_DIG and 5V5_PRE")
s.note("TPS563208 (FCCM, fixed 580 kHz). Feedback taken before the solder jumper so each buck "
       "regulates with its jumper open (bring-up step 1). Inductors 4.7 uH: Table 7-2 maximum.")
for n, (ref_u, out, rtop, jp) in enumerate((("U2", "5V_DIG", "54.9k 1%", "JP1"),
                                           ("U3", "5V5_PRE", "61.9k 1%", "JP2"))):
    k = n + 1
    reg = f"{out}_REG"
    i = 10 * k
    if n:
        s.row()
    s.part("Regulator_Switching:TPS563208", ref_u, "TPS563208DDCR",
           "Package_TO_SOT_SMD:TSOT-23-6",
           {"VIN": "12V_P", "GND": "GND", "EN": f"BUCK{k}_EN", "SW": f"BUCK{k}_SW",
            "VBST": f"BUCK{k}_BST", "VFB": f"BUCK{k}_FB"})
    s.c(f"C{i}", "10u 25V", "12V_P", "GND", fp=C1206)
    s.c(f"C{i + 1}", "10u 25V", "12V_P", "GND", fp=C1206)
    s.c(f"C{i + 2}", "100n 50V", "12V_P", "GND")
    s.r(f"R{i}", "100k", "12V_P", f"BUCK{k}_EN")
    s.r(f"R{i + 1}", "47k", f"BUCK{k}_EN", "GND")
    s.c(f"C{i + 3}", "100n 25V", f"BUCK{k}_BST", f"BUCK{k}_SW")
    s.l(f"L{k}", "4.7u SRN6045TA-4R7M", f"BUCK{k}_SW", reg,
        "Inductor_SMD:L_Bourns_SRN6045TA")
    s.r(f"R{i + 2}", rtop, reg, f"BUCK{k}_FB")
    s.r(f"R{i + 3}", "10k 1%", f"BUCK{k}_FB", "GND")
    s.c(f"C{i + 4}", "22u 16V", reg, "GND", fp=C1206)
    s.c(f"C{i + 5}", "22u 16V", reg, "GND", fp=C1206)
    sj(s, jp, reg, out)
    s.flag(out)

# ------------------------------------------------------------------ 3. isolated analogue supply
s = b.sheet("iso_supply", "Isolated supply: +15V_RAW and -15V_RAW")
s.note("PS1 WRA1215S-3WR2: PIN NUMBERS UNVERIFIED (from a drawing). Check against the "
       "datasheet's Dimensions and Recommended Layout before layout. Ctrl open = on.")
s.note("Capacitance per output on D: 10 u + 100 u = 110 uF. With board A's LDO input "
       "capacitors it must stay under 220 uF (YLPTEC listing; Mornsun allows 680 uF).")
s.cp("C30", "100u 25V", "12V_P", "GND", "Capacitor_SMD:CP_Elec_6.3x7.7", fields=HAND)
s.l("L3", "4.7u SRN4018-4R7M", "12V_P", "ISO_VIN", "Inductor_SMD:L_Bourns-SRN4018")
s.cp("C31", "47u 25V", "ISO_VIN", "GND", "Capacitor_SMD:CP_Elec_6.3x7.7", fields=HAND)
s.part("rev_a:WRA1215S-3WR2", "PS1", "WRA1215S-3WR2",
       "Connector_PinHeader_2.54mm:PinHeader_1x08_P2.54mm_Vertical",
       {"Vin": "ISO_VIN", "GND": "GND", "+Vo": "+15V_MOD", "0V": "GND", "-Vo": "-15V_MOD"},
       nc=["Ctrl"], fields=HAND)
s.flag("ISO_VIN")
s.row()
s.c("C32", "10u 50V", "+15V_MOD", "GND", fp=C1210)
s.l("L4", "10u SRN4018-100M", "+15V_MOD", "+15V_FILT", "Inductor_SMD:L_Bourns-SRN4018")
s.cp("C33", "100u 50V", "+15V_FILT", "GND", "Capacitor_SMD:CP_Elec_8x10", fields=HAND)
s.r("R30", "3.0k 1206", "+15V_FILT", "GND", fp=R1206, dnp=True)
sj(s, "JP3", "+15V_FILT", "+15V_RAW")
s.flag("+15V_RAW")
s.row()
s.c("C34", "10u 50V", "GND", "-15V_MOD", fp=C1210)
s.l("L5", "10u SRN4018-100M", "-15V_MOD", "-15V_FILT", "Inductor_SMD:L_Bourns-SRN4018")
s.cp("C35", "100u 50V", "GND", "-15V_FILT", "Capacitor_SMD:CP_Elec_8x10", fields=HAND)
s.r("R31", "3.0k 1206", "GND", "-15V_FILT", fp=R1206, dnp=True)
sj(s, "JP4", "-15V_FILT", "-15V_RAW")
s.flag("-15V_RAW")

# ------------------------------------------------------------------ 4. supervisor
s = b.sheet("supervisor", "Supervisor: RAILS_OK")
s.note("RAILS_OK low below 12V_P = 10.47 V, high 189 ms after 12V_P rises above about 10.9 V. "
       "R42 from the output adds hysteresis. Open drain, pulled up on D only.")
s.part("Power_Supervisor:TPS3808DBV", "U4", "TPS3808G01DBVR", "Package_TO_SOT_SMD:SOT-23-6",
       {"VDD": "NUCLEO_3V3", "GND": "GND", "SENSE": "UV_SENSE", "CT": "SUP_CT",
        "~{RESET}": "RAILS_OK"}, nc=["~{MR}"])
s.c("C40", "100n 16V", "NUCLEO_3V3", "GND")
s.r("R40", "255k 1%", "12V_P", "UV_SENSE")
s.r("R41", "10k 1%", "UV_SENSE", "GND")
s.r("R42", "2.8M 1%", "RAILS_OK", "UV_SENSE")
s.c("C41", "1n 50V", "UV_SENSE", "GND")
s.c("C42", "33n 16V X7R", "SUP_CT", "GND")
s.r("R43", "10k", "RAILS_OK", "NUCLEO_3V3")

# ------------------------------------------------------------------ 5. Nucleo
s = b.sheet("nucleo", "Nucleo morpho sockets")
s.note("J2 = CN11, J3 = CN12 (UM2408 Table 19). JP2 on the Nucleo must sit on 5-6 (EXT). "
       "CN12-12 and CN12-14 as shipped carry PA12 and PA11 [Verify, V30]. 5V_EXT load [Verify, V29].")
CN11 = {
    1: "BTN3_MCU", 2: "BTN4_MCU", 3: "BTN5_MCU", 4: "ENC1_SW_MCU", 5: "NUCLEO_VDD",
    6: "5V_DIG", 7: "BOOT0", 8: "GND", 9: "LED7_MCU", 16: "NUCLEO_3V3", 19: "GND", 20: "GND",
    22: "GND", 32: "POT3_ADC", 38: "POT2_ADC", 39: "RAILS_OK", 40: "CODEC_RST_N",
    41: "OSC_SEL", 43: "OSC_22M_EN", 45: "SPDIF_RX", 47: "DOUT1", 48: "LRCK_MCU", 49: "GND",
    50: "BCK_MCU", 55: "BTN2_MCU", 57: "BTN1_MCU", 60: "GND", 62: "DIN1_MCU",
}
CN12 = {
    1: "MCLK_MCU", 3: "I2C1_SCL", 4: "ENC1_A_MCU", 5: "I2C1_SDA", 7: "VREFP", 9: "GND",
    11: "POT4_ADC", 12: "USB_D_P", 13: "POT5_ADC", 14: "USB_D_N", 18: "LED6_MCU",
    19: "ENC1_B_MCU", 20: "GND", 24: "POT6_ADC", 25: "LED5_MCU", 32: "POT_GND",
    37: "POT1_ADC", 39: "GND", 40: "MUTE_LINE34", 41: "ENC2_B_MCU", 43: "ENC2_A_MCU",
    44: "MUTE_MON", 45: "SPDIF_TX", 47: "HP_EN", 49: "CODEC_OVF", 50: "I2C4_SCL_MCU",
    51: "LED4_MCU", 52: "LED1_MCU", 53: "VBUS_DET", 54: "GND", 55: "LED3_MCU",
    56: "LED2_MCU", 60: "I2C4_SDA_MCU", 61: "ENC2_SW_MCU", 62: "POT7_ADC", 63: "GND",
}
SOCKET = "Connector_PinSocket_2.54mm:PinSocket_2x35_P2.54mm_Vertical"
for ref, table in (("J2", CN11), ("J3", CN12)):
    s.part("Connector_Generic:Conn_02x35_Odd_Even", ref, "CN11" if ref == "J2" else "CN12",
           SOCKET, {str(k): v for k, v in table.items()},
           nc=[str(n) for n in range(1, 71) if n not in table], fields=HAND)
s.flag("NUCLEO_3V3")
s.row()
s.c("C50", "10u 10V", "5V_DIG", "GND", fp=C1206)
s.c("C51", "10u 10V", "NUCLEO_3V3", "GND", fp=C1206)
s.c("C52", "100n 16V", "NUCLEO_3V3", "GND")
s.part("Connector_Generic:Conn_01x02", "J4", "BOOT0 open",
       "Connector_PinHeader_2.54mm:PinHeader_1x02_P2.54mm_Vertical",
       {"1": "NUCLEO_VDD", "2": "BOOT0"}, fields=HAND)
s.row()
# Series terminations at the driving end (D drives BCK, LRCK, DIN1).
s.r("R50", "33", "BCK_MCU", "BCK")
s.r("R51", "33", "LRCK_MCU", "LRCK")
s.r("R52", "33", "DIN1_MCU", "DIN1")
s.r("R53", "2.2k", "I2C1_SCL", "NUCLEO_3V3")
s.r("R54", "2.2k", "I2C1_SDA", "NUCLEO_3V3")

# ------------------------------------------------------------------ 6. USB-C
s = b.sheet("usb", "USB-C")
s.note("Device port, USB 2.0 full speed, data only. VBUS is sensed (PE15), never a supply. "
       "Shell to CHASSIS; R62 and C61 are the optional shell-to-GND parts (DNP).")
s.part("Connector:USB_C_Receptacle_USB2.0_16P", "J5", "USB4105-GF-A",
       "Connector_USB:USB_C_Receptacle_GCT_USB4105-xx-A_16P_TopMnt_Horizontal",
       {"GND": "GND", "VBUS": "USB_VBUS", "CC1": "USB_CC1", "CC2": "USB_CC2",
        "D+": "USB_D_P", "D-": "USB_D_N", "SHIELD": "CHASSIS"}, nc=["SBU1", "SBU2"])
s.r("R60", "5.1k 1%", "USB_CC1", "GND")
s.r("R61", "5.1k 1%", "USB_CC2", "GND")
s.part("Power_Protection:USBLC6-2SC6", "U5", "USBLC6-2SC6", "Package_TO_SOT_SMD:SOT-23-6",
       {"I/O1": "USB_D_P", "I/O2": "USB_D_N", "VBUS": "USB_VBUS", "GND": "GND"})
s.c("C60", "1u 25V", "USB_VBUS", "GND")
s.r("R63", "100k 1%", "USB_VBUS", "VBUS_DET")
s.r("R64", "200k 1%", "VBUS_DET", "GND")
s.row()
s.r("R62", "1M", "CHASSIS", "GND", dnp=True)
s.c("C61", "4.7n 100V", "CHASSIS", "GND", dnp=True)

# ------------------------------------------------------------------ 7. optical
s = b.sheet("optical", "Optical S/PDIF (batch 10, not fitted)")
s.note("Batch 10 parts: U6, U7 and their supply parts are DNP. PLR135 and PLT133 PIN NUMBERS "
       "UNVERIFIED. The PLR135 is obsolete at Digi-Key: a current receiver in its footprint [V25].")
s.fb("FB70", "BLM18PG221SN1", "NUCLEO_3V3", "OPT_RX_VCC", dnp=True)
s.c("C70", "100n 16V", "OPT_RX_VCC", "GND", dnp=True)
s.part("rev_a:PLR135", "U6", "PLR135/T9", "OptoDevice:Toshiba_TORX170_TORX173_TORX193_TORX194",
       {"VCC": "OPT_RX_VCC", "GND": "GND", "VOUT": "SPDIF_RX"}, dnp=True, fields=HAND)
s.flag("OPT_RX_VCC")
s.row()
s.c("C71", "100n 16V", "NUCLEO_3V3", "GND", dnp=True)
s.part("rev_a:PLT133", "U7", "PLT133/T10W", "OptoDevice:Toshiba_TOTX170_TOTX173_TOTX193_TOTX194",
       {"VCC": "NUCLEO_3V3", "GND": "GND", "VIN": "SPDIF_TX"}, dnp=True, fields=HAND)

# ------------------------------------------------------------------ 8. panel interface
s = b.sheet("panel", "Panel interface: J_PANEL")
s.note("POT_REF: U8 follows VREFP (dual feedback: R81 to POT_REF for DC, C81 for stability). "
       "U8 runs from 5V_DIG: VREF+ equals the Nucleo's 3V3, so a 3.3 V follower could not reach it.")
s.note("Bypass: fit R83 only with R80 removed (U8 would otherwise drive VREFP through 47 ohm).")
pins, nc = links.pins("J_PANEL")
s.part("Connector_Generic:Conn_02x20_Odd_Even", "J6", "J_PANEL", IDC_2X20, pins, nc=nc,
       fields=HAND)
s.row()
s.part("Amplifier_Operational:TLV9001IDCK", "U8", "TLV9001IDCKR",
       "Package_TO_SOT_SMD:SOT-353_SC-70-5",
       {"+": "VREFP", "-": "POTBUF_FB", "V+": "5V_DIG", "V-": "GND", "4": "POTBUF_OUT"})
s.c("C80", "100n 16V", "5V_DIG", "GND")
s.r("R80", "47", "POTBUF_OUT", "POT_REF")
s.c("C82", "1u 10V X7R", "POT_REF", "POT_GND")
s.r("R81", "10k", "POT_REF", "POTBUF_FB")
s.c("C81", "330n 16V X7R", "POTBUF_OUT", "POTBUF_FB")
s.r("R83", "0", "VREFP", "POT_REF", dnp=True)
s.row()
for k in range(1, 8):  # Wipers: 1 k and 100 nF to POT_GND at the MCU end (11.2).
    s.r(f"R{100 + k}", "1k", f"POT{k}", f"POT{k}_ADC")
    s.c(f"C{100 + k}", "100n 16V", f"POT{k}_ADC", "POT_GND")
s.row()
switches = [(f"BTN{k}", "10n 16V") for k in range(1, 6)] + [
    ("ENC1_A", "1n 50V"), ("ENC1_B", "1n 50V"), ("ENC1_SW", "10n 16V"),
    ("ENC2_A", "1n 50V"), ("ENC2_B", "1n 50V"), ("ENC2_SW", "10n 16V")]
for k, (line, cap) in enumerate(switches, start=1):  # 11.3: pull-up, 1 k, C at the pin.
    s.r(f"R{110 + k}", "10k", line, "NUCLEO_3V3")
    s.r(f"R{130 + k}", "1k", line, f"{line}_MCU")
    s.c(f"C{110 + k}", cap, f"{line}_MCU", "GND")
s.row()
for k in range(1, 8):  # LED lines: series resistor at the MCU end (section 9).
    s.r(f"R{150 + k}", "150", f"LED{k}_MCU", f"LED{k}")
s.row()
for k, line in enumerate(("I2C4_SCL", "I2C4_SDA")):
    s.r(f"R{160 + k}", "100", f"{line}_MCU", line)
    s.r(f"R{162 + k}", "4.7k", f"{line}_MCU", "NUCLEO_3V3")
s.fb("FB80", "BLM18PG221SN1", "NUCLEO_3V3", "PANEL_3V3")
s.c("C83", "10u 10V", "PANEL_3V3", "GND", fp=C1206)
s.c("C84", "100n 16V", "PANEL_3V3", "GND")

# ------------------------------------------------------------------ 9. link
s = b.sheet("link", "Link to board A: J_LINK")
s.note("Pin-out from hw/tools/links.py (rev_a_board_split.md 3.1). Series resistors for BCK, "
       "LRCK and DIN1 are on the Nucleo sheet; DOUT1 and MCLK_MCU are terminated on A.")
pins, nc = links.pins("J_LINK")
s.part("Connector_Generic:Conn_02x20_Odd_Even", "J7", "J_LINK", IDC_2X20, pins, nc=nc,
       fields=HAND)

# ------------------------------------------------------------------ 10. mechanical, test points
s = b.sheet("mech", "Mechanical and test points")
s.note("H1 is the single chassis bond, next to J5 and J1 (section 7): R90 fitted, or C90 with "
       "R91 instead. H2 to H4 are unplated and unconnected; insulating standoffs only.")
s.part("Mechanical:MountingHole_Pad", "H1", "M3 bond", "MountingHole:MountingHole_3.2mm_M3_Pad_Via",
       {"1": "CHASSIS"})
s.r("R90", "0 1206", "CHASSIS", "GND", fp=R1206)
s.c("C90", "10n 100V", "CHASSIS", "GND", dnp=True)
s.r("R91", "1M", "CHASSIS", "GND", dnp=True)
for k in (2, 3, 4):
    s.part("Mechanical:MountingHole", f"H{k}", "M3", "MountingHole:MountingHole_3.2mm_M3", {})
s.flag("CHASSIS")
s.row()
TPS = ["12V_IN", "12V_P", "5V_DIG_REG", "5V5_PRE_REG", "+15V_FILT", "-15V_FILT", "NUCLEO_3V3",
       "VREFP", "POT_REF", "RAILS_OK", "MCLK_MCU", "BCK", "LRCK", "DIN1", "DOUT1", "I2C1_SCL",
       "I2C1_SDA"]
for k, net in enumerate(TPS, start=1):
    s.part("Connector:TestPoint", f"TP{k}", net, TP_PAD, {"1": net})
for k, where in ((len(TPS) + 1, "GND power"), (len(TPS) + 2, "GND digital")):
    s.part("Connector:TestPoint", f"TP{k}", where, TP_POST, {"1": "GND"}, fields=HAND)

# ------------------------------------------------------------------ write and check
b.write()
counts = {sh.title: len({u.ref for u in sh.units if u is not None}) for sh in b.sheets}
for title, n in counts.items():
    print(f"{n:4d}  {title}")
print(f"{sum(counts.values()):4d}  parts in total")
found = b.erc()
for v in found:
    print(v)
errors = [v for v in found if v.startswith("error")]
print(f"ERC: {len(errors)} errors, {len(found) - len(errors)} warnings")
sys.exit(1 if errors else 0)
