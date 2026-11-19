"""Rev A board A, converter and analogue (batch 5, stage 3).

    python hw/rev-a/a/design.py

Writes the KiCad project in this folder, runs KiCad's ERC and exits non-zero on any ERC error.
The circuit follows docs/notes/rev_a_architecture.md, rev_a_input_budget.md and
rev_a_board_split.md; every value, its derivation and every deviation is in NOTES.md here.
"""
import pathlib
import sys

HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parents[1] / "tools"))
from kisch import Board  # noqa: E402
import links  # noqa: E402

# ---------------------------------------------------------------- footprints and parts

R0603 = "Resistor_SMD:R_0603_1608Metric"
R1206 = "Resistor_SMD:R_1206_3216Metric"
C0603 = "Capacitor_SMD:C_0603_1608Metric"
C0805 = "Capacitor_SMD:C_0805_2012Metric"
C1206 = "Capacitor_SMD:C_1206_3216Metric"
CP4 = "Capacitor_SMD:CP_Elec_4x5.4"
CP5 = "Capacitor_SMD:CP_Elec_5x5.4"
CP63 = "Capacitor_SMD:CP_Elec_6.3x7.7"
SOIC8 = "Package_SO:SOIC-8_3.9x4.9mm_P1.27mm"
SOT23 = "Package_TO_SOT_SMD:SOT-23"
SOT235 = "Package_TO_SOT_SMD:SOT-23-5"
SOT236 = "Package_TO_SOT_SMD:SOT-23-6"
SSOP8 = "Package_SO:SSOP-8_2.95x2.8mm_P0.65mm"  # TI DCT
SOD123 = "Diode_SMD:D_SOD-123"
SOD323 = "Diode_SMD:D_SOD-323"
L1210 = "Inductor_SMD:L_1210_3225Metric"
TP_SIG = "TestPoint:TestPoint_Pad_D1.0mm"
TP_RAIL = "TestPoint:TestPoint_Pad_D1.5mm"
JACK = "Connector_Audio:NMJ6HCD2"
JACK_FP = "Connector_Audio:Jack_6.35mm_Neutrik_NMJ6HCD2_Horizontal"
RELAY = "Relay:Omron_G6K-2"
RELAY_FP = "Relay_SMD:Relay_DPDT_Omron_G6K-2F-Y"
OPA1678 = "Amplifier_Operational:OPA1678"
TVS = "Device:D_TVS"
TVS_VAL = "TVS bidir 15V (PESD15VL1BA)"
HAND = {"Fit": "hand"}

RAILS = ["+15V_RAW", "-15V_RAW", "5V5_PRE", "5V_DIG", "+12V_ANA", "-12V_ANA", "5V_ANA", "3V3_A"]


def refs(base):
    """Reference designators numbered from base on each sheet: R101, R102, ..."""
    count = {}

    def nxt(prefix):
        count[prefix] = count.get(prefix, 0) + 1
        return f"{prefix}{base + count[prefix]}"
    return nxt


def opamp_power(s, nx, u, lib=OPA1678, value="OPA1678IDR", fp=SOIC8, unit=3):
    s.part(lib, u, value, fp, {"V+": "+12V_ANA", "V-": "-12V_ANA"}, unit=unit)
    s.c(nx("C"), "100n 50V", "+12V_ANA", "GND")
    s.c(nx("C"), "100n 50V", "-12V_ANA", "GND")


def rail_bulk(s, nx):
    s.c(nx("C"), "10u 25V X7R", "+12V_ANA", "GND", fp=C1206)
    s.c(nx("C"), "10u 25V X7R", "-12V_ANA", "GND", fp=C1206)


# ---------------------------------------------------------------- 1. link

def sheet_link(b):
    s = b.sheet("link", "Link to board D")
    nx = refs(100)
    s.note("J_LINK from board D (rev_a_board_split.md 3.1). Pin-out from hw/tools/links.py.")
    s.note("Series 33 ohm at A's drivers only: DOUT1 on the converter sheet, MCLK_MCU on the "
           "clocks sheet. I2C pull-ups and the RAILS_OK pull-up are on D.")
    s.note("Pull-downs: an unplugged cable or a reset MCU (pins high-impedance) mutes everything "
           "and holds the converter in reset. Place each next to the part it controls.")
    pins, nc = links.pins("J_LINK")
    s.part("Connector_Generic:Conn_02x20_Odd_Even", "J101", "J_LINK",
           "Connector_IDC:IDC-Header_2x20_P2.54mm_Vertical", pins, nc=nc, fields=HAND)
    s.row()
    for net in ("CODEC_RST_N", "MUTE_MON", "MUTE_LINE34", "HP_EN", "OSC_22M_EN"):
        s.r(nx("R"), "10k", net, "GND")
    s.r(nx("R"), "10k", "3V3_A", "OSC_SEL")
    s.row()
    s.c(nx("C"), "10u 16V", "5V_DIG", "GND", fp=C0805)
    for net in ("GND", "5V_DIG", "5V5_PRE", "+15V_RAW", "-15V_RAW"):
        s.flag(net)


# ---------------------------------------------------------------- 2. power

def sheet_power(b):
    s = b.sheet("power", "Linear regulators")
    nx = refs(200)
    s.note("Board A has only linear regulators. Each output reaches its rail through a 0 ohm "
           "link, open for bring-up unloaded (architecture 14).")
    s.note("Raw rails: 100u + 10u = 110 uF each on A, 110 uF on D after its LC: 220 uF, the "
           "module's maximum load. Keep it so (architecture 5.3, 8; board D).")
    # +12V_ANA: TPS7A4901, Vout = 1.194 V x (1 + 90.9k / 10.0k) = 12.05 V (SBVS121E 9.1.1).
    s.cp(nx("C"), "100u 25V", "+15V_RAW", "GND", CP63)
    s.c(nx("C"), "10u 25V X7R", "+15V_RAW", "GND", fp=C1206)
    s.part("rev_a:TPS7A4901", "U201", "TPS7A4901DGNR",
           "Package_SO:HVSSOP-8-1EP_3x3mm_P0.65mm_EP1.57x1.89mm_ThermalVias",
           {"IN": "+15V_RAW", "EN": "+15V_RAW", "NR/SS": "P12_NR", "OUT": "+12V_ANA_REG",
            "FB": "P12_FB", "GND": "GND", "PAD": "GND"}, nc=["NC", "DNC"])
    s.c(nx("C"), "10n 50V C0G", "P12_NR", "GND")
    s.r(nx("R"), "90.9k 1%", "+12V_ANA_REG", "P12_FB")
    s.c(nx("C"), "10n 50V C0G", "+12V_ANA_REG", "P12_FB")
    s.r(nx("R"), "10.0k 1%", "P12_FB", "GND")
    s.c(nx("C"), "10u 25V X7R", "+12V_ANA_REG", "GND", fp=C1206)
    s.r(nx("R"), "0R", "+12V_ANA_REG", "+12V_ANA")
    s.row()
    # -12V_ANA: TPS7A3001, R1 93.1k, R2 10.0k for -12 V (SBVS125D Table 2).
    s.cp(nx("C"), "100u 25V", "GND", "-15V_RAW", CP63)
    s.c(nx("C"), "10u 25V X7R", "-15V_RAW", "GND", fp=C1206)
    s.part("rev_a:TPS7A3001", "U202", "TPS7A3001DGNR",
           "Package_SO:HVSSOP-8-1EP_3x3mm_P0.65mm_EP1.57x1.89mm_ThermalVias",
           {"IN": "-15V_RAW", "EN": "-15V_RAW", "NR/SS": "N12_NR", "OUT": "-12V_ANA_REG",
            "FB": "N12_FB", "GND": "GND", "PAD": "GND"}, nc=["NC", "DNC"])
    s.c(nx("C"), "10n 50V C0G", "N12_NR", "GND")
    s.r(nx("R"), "93.1k 1%", "-12V_ANA_REG", "N12_FB")
    s.c(nx("C"), "10n 50V C0G", "-12V_ANA_REG", "N12_FB")
    s.r(nx("R"), "10.0k 1%", "N12_FB", "GND")
    s.c(nx("C"), "10u 25V X7R", "-12V_ANA_REG", "GND", fp=C1206)
    s.r(nx("R"), "0R", "-12V_ANA_REG", "-12V_ANA")
    s.row()
    # 5V_ANA: LC filter (2.2 uH, 22 uF, architecture 5.2), TPS7A2050 in SOT-23-5.
    s.l(nx("L"), "2.2u 0.5A", "5V5_PRE", "5V5_LC", L1210)
    s.c(nx("C"), "22u 10V X5R", "5V5_LC", "GND", fp=C1206)
    s.part("Regulator_Linear:TPS7A20xxxDBV", "U203", "TPS7A2050PDBVR", SOT235,
           {"IN": "5V5_LC", "EN": "5V5_LC", "GND": "GND", "OUT": "5V_ANA_REG"}, nc=["4"])
    s.c(nx("C"), "10u 16V X7R", "5V_ANA_REG", "GND", fp=C0805)
    s.r(nx("R"), "0R", "5V_ANA_REG", "5V_ANA")
    s.row()
    # 3V3_A: 4.7 ohm ahead of the TPS7A2033 shares its dissipation and filters 5V5_PRE.
    s.r(nx("R"), "4.7R 1206", "5V5_PRE", "5V5_RC", fp=R1206)
    s.c(nx("C"), "10u 16V X7R", "5V5_RC", "GND", fp=C0805)
    s.part("Regulator_Linear:TPS7A20xxxDBV", "U204", "TPS7A2033PDBVR", SOT235,
           {"IN": "5V5_RC", "EN": "5V5_RC", "GND": "GND", "OUT": "3V3_A_REG"}, nc=["4"])
    s.c(nx("C"), "10u 16V X7R", "3V3_A_REG", "GND", fp=C0805)
    s.r(nx("R"), "0R", "3V3_A_REG", "3V3_A")
    for net in ("+12V_ANA", "-12V_ANA", "5V_ANA", "3V3_A", "5V5_LC", "5V5_RC"):
        s.flag(net)  # Driven through a link, inductor or resistor, which ERC cannot see through.


# ---------------------------------------------------------------- 3. clocks

def sheet_clocks(b):
    s = b.sheet("clocks", "Clocks")
    nx = refs(300)
    s.note("OSC_SEL high (its pull-up, the default): 24.576 MHz enabled and selected "
           "(pin_plan.md). 74LVC1G97 as a 2:1 mux: In2 low gives In1, In2 high gives In0.")
    s.note("74LVC1G97 replaces the 74LVC1G157 of stage 2 (no KiCad symbol for the 157). "
           "100k pull-downs hold a disabled (tri-stated) oscillator's mux input low.")
    for x, mhz, en, out in (("X301", "24.576MHz", "OSC_SEL", "OSC_24M"),
                            ("X302", "22.5792MHz", "OSC_22M_EN", "OSC_22M")):
        vdd = out + "_VDD"
        s.fb(nx("FB"), "600R@100MHz", "3V3_A", vdd)
        s.c(nx("C"), "10u 10V X7R", vdd, "GND", fp=C0805)
        s.c(nx("C"), "100n", vdd, "GND")
        s.part("Oscillator:ASE-xxxMHz", x, f"{mhz} 3V3 CMOS OE",
               "Oscillator:Oscillator_SMD_Abracon_ASE-4Pin_3.2x2.5mm",
               {"EN": en, "GND": "GND", "OUT": out + "_SRC", "Vdd": vdd})
        s.r(nx("R"), "33R", out + "_SRC", out)
        s.r(nx("R"), "100k", out, "GND")
        s.flag(vdd)  # Fed through the ferrite.
        s.row()
    s.part("74xGxx:74LVC1G97", "U301", "74LVC1G97DBVR", SOT236,
           {"IN0": "OSC_24M", "IN1": "OSC_22M", "IN2": "OSC_SEL", "Y": "MCLK_MUX",
            "VCC": "3V3_A", "GND": "GND"})
    s.c(nx("C"), "100n", "3V3_A", "GND")
    s.part("74xGxx:74LVC2G34", "U302", "74LVC2G34DBVR", SOT236, {"1": "MCLK_MUX", "6": "SCKI_SRC"})
    s.part("74xGxx:74LVC2G34", "U302", "74LVC2G34DBVR", SOT236,
           {"3": "MCLK_MUX", "4": "MCLK_MCU_SRC"}, unit=2)
    s.part("74xGxx:74LVC2G34", "U302", "74LVC2G34DBVR", SOT236, {"5": "3V3_A", "2": "GND"},
           unit=3)
    s.c(nx("C"), "100n", "3V3_A", "GND")
    s.r(nx("R"), "33R", "SCKI_SRC", "SCKI")
    s.r(nx("R"), "33R", "MCLK_MCU_SRC", "MCLK_MCU")


# ---------------------------------------------------------------- 4. converter

def sheet_converter(b):
    s = b.sheet("converter", "Converter PCM3168A")
    nx = refs(400)
    s.note("I2C control: MODE tied to DGND (SBAS452A pin 48; through 0 ohm for a test point). "
           "ADR1 = ADR0 = 0: address 0b1000100 = 0x44 (9.3.14).")
    s.note("Unused ADCs 3 to 6: + and - joined, 100 nF to AGNDAD (12.1.3, second method). "
           "DACs 7, 8, DOUT3 and ZERO open. DIN3, DIN4 to DGND; DIN2 10k to DGND and a pad.")
    s.note("Decoupling per supply pin: 1 uF ceramic at the pin plus 10 uF electrolytic "
           "(12.1.1); 10 uF electrolytic on VCOMAD, VCOMDA, VREFAD1, VREFAD2 (12.1.4, 12.1.5).")
    pins = {
        "4": "CODEC_RST_N", "5": "CODEC_OVF", "48": "CODEC_MODE",
        "42": "I2C1_SCL", "43": "I2C1_SDA", "44": "CODEC_ADR1", "45": "CODEC_ADR0",
        "41": "SCKI", "6": "LRCK", "35": "LRCK", "7": "BCK", "36": "BCK",
        "37": "DIN1", "38": "CODEC_DIN2", "39": "GND", "40": "GND",
        "8": "DOUT1_SRC", "9": "CODEC_DOUT2",
        "52": "ADC1_P", "51": "ADC1_N", "54": "ADC2_P", "53": "ADC2_N",
        "56": "ADC3_TERM", "55": "ADC3_TERM", "58": "ADC4_TERM", "57": "ADC4_TERM",
        "62": "ADC5_TERM", "61": "ADC5_TERM", "64": "ADC6_TERM", "63": "ADC6_TERM",
        "59": "VREFAD1", "60": "VREFAD2", "1": "VCOMAD", "15": "VCOMDA",
        "49": "5V_ANA", "3": "5V_ANA", "14": "5V_ANA", "34": "5V_ANA",
        "46": "3V3_A", "12": "3V3_A",
        "50": "GND", "2": "GND", "16": "GND", "33": "GND", "47": "GND", "11": "GND",
        "65": "GND",
    }
    for dac, (p, n) in enumerate((("31", "32"), ("29", "30"), ("27", "28"), ("25", "26"),
                                  ("23", "24"), ("21", "22")), start=1):
        pins[p] = f"DAC{dac}_P"
        pins[n] = f"DAC{dac}_N"
    s.part("rev_a:PCM3168A", "U401", "PCM3168APAPR",
           "Package_QFP:Texas_TQFP-64-1EP_10x10mm_P0.5mm_EP8x8mm_Mask5x5mm_ThermalVias", pins,
           nc=["17", "18", "19", "20", "10", "13"])
    s.row()
    s.r(nx("R"), "0R", "CODEC_MODE", "GND")
    s.r(nx("R"), "10k", "CODEC_ADR0", "GND")
    s.r(nx("R"), "10k", "CODEC_ADR1", "GND")
    s.r(nx("R"), "10k", "CODEC_DIN2", "GND")
    s.r(nx("R"), "33R", "DOUT1_SRC", "DOUT1")
    for net in ("ADC3_TERM", "ADC4_TERM", "ADC5_TERM", "ADC6_TERM"):
        s.c(nx("C"), "100n", net, "GND")
    s.row()
    for pin, rail in (("49", "5V_ANA"), ("3", "5V_ANA"), ("14", "5V_ANA"), ("34", "5V_ANA"),
                      ("46", "3V3_A"), ("12", "3V3_A")):
        near = {"Near": f"U401 pin {pin}"}
        s.c(nx("C"), "1u 16V X7R", rail, "GND", fields=near)
        s.cp(nx("C"), "10u 16V", rail, "GND", CP4, fields=near)
    s.row()
    for net in ("VCOMAD", "VCOMDA", "VREFAD1", "VREFAD2"):
        s.cp(nx("C"), "10u 16V", net, "GND", CP4)


# ---------------------------------------------------------------- 5. inputs

def sheet_inputs(b):
    s = b.sheet("inputs", "Line inputs 1 and 2")
    nx = refs(500)
    s.note("Per leg (rev_a_input_budget.md, architecture 9): 100R and 470p to chassis (RF), "
           "TVS to chassis, 1M bleed, coupling cap, inverting stage Rin 20.0k, Rf 5.11k "
           "(G = 0.2555, 0 dBFS = +20.1 dBu), + input on VCOMAD, 47R and 10n into the ADC.")
    s.note("The hot leg (tip) drives VINx- and the cold leg VINx+: the stage inverts, so the "
           "channel's polarity is kept.")
    for ch in (1, 2):
        tip, ring = f"IN{ch}_TIP", f"IN{ch}_RING"
        s.part(JACK, nx("J"), "NMJ6HCD2", JACK_FP, {"T": tip, "R": ring, "S": "CHASSIS"},
               nc=["TN", "RN", "SN"], fields=HAND)
        u = nx("U")
        legs = (("H", tip, f"ADC{ch}_N", 1, ("1", "2", "3")),
                ("C", ring, f"ADC{ch}_P", 2, ("7", "6", "5")))
        for leg, src, adc, unit, (o, m, p) in legs:
            n = f"IN{ch}_{leg}"
            s.r(nx("R"), "100R", src, n + "_RF")
            s.c(nx("C"), "470p 50V C0G", n + "_RF", "CHASSIS")
            s.part(TVS, nx("D"), TVS_VAL, SOD323, {"1": n + "_RF", "2": "CHASSIS"})
            s.r(nx("R"), "1M", n + "_RF", "GND")
            s.cp(nx("C"), "10u 35V", n + "_AC", n + "_RF", CP5)
            s.r(nx("R"), "20.0k 0.1%", n + "_AC", n + "_INV")
            s.r(nx("R"), "5.11k 0.1%", n + "_INV", n + "_OUT")
            s.c(nx("C"), "100p 50V C0G", n + "_INV", n + "_OUT")
            s.part(OPA1678, u, "OPA1678IDR", SOIC8, {o: n + "_OUT", m: n + "_INV", p: "VCOMAD"},
                   unit=unit)
            s.r(nx("R"), "47R", n + "_OUT", adc)
            s.row()
        opamp_power(s, nx, u)
        s.c(nx("C"), "10n 50V C0G", f"ADC{ch}_P", f"ADC{ch}_N", fp=C0805)
        s.row()
    rail_bulk(s, nx)


# ---------------------------------------------------------------- 6, 7. output stages

def out_channel(s, nx, name, dac, coil):
    """One balanced output: per leg AC coupling, MFB low-pass (gain -11k/5.1k = -2.157), 100R
    build-out, a DPDT relay (NO to the stage, COM to the jack side, NC to GND), 10k bleed and a
    TVS to chassis on the jack side. Returns the hot and cold jack-side nets."""
    hot, cold = f"{name}_HOT", f"{name}_COLD"
    u = nx("U")
    k = nx("K")
    # The stage inverts, so VOUTx- feeds the hot leg and VOUTx+ the cold leg.
    legs = (("H", f"DAC{dac}_N", hot, 1, ("1", "2", "3")),
            ("C", f"DAC{dac}_P", cold, 2, ("7", "6", "5")))
    for leg, src, jack_side, unit, (o, m, p) in legs:
        n = f"{name}_{leg}"
        s.cp(nx("C"), "22u 16V", src, n + "_AC", CP4)
        s.r(nx("R"), "5.1k", n + "_AC", n + "_SUM")
        s.c(nx("C"), "6.8n 50V C0G", n + "_SUM", "GND", fp=C0805)
        s.r(nx("R"), "11k", n + "_SUM", n + "_OUT")
        s.r(nx("R"), "360R", n + "_SUM", n + "_INV")
        s.c(nx("C"), "330p 50V C0G", n + "_INV", n + "_OUT")
        s.part(OPA1678, u, "OPA1678IDR", SOIC8, {o: n + "_OUT", m: n + "_INV", p: "GND"},
               unit=unit)
        s.r(nx("R"), "100R", n + "_OUT", n + "_BO")
        s.r(nx("R"), "10k", jack_side, "GND")
        s.part(TVS, nx("D"), TVS_VAL, SOD323, {"1": jack_side, "2": "CHASSIS"})
        s.row()
    s.part(RELAY, k, "G6K-2F-Y DC5", RELAY_FP,
           {"11": hot, "12": "GND", "14": f"{name}_H_BO",
            "21": cold, "22": "GND", "24": f"{name}_C_BO", "A1": "5V_DIG", "A2": coil})
    opamp_power(s, nx, u)
    return hot, cold


def sheet_monitor(b):
    s = b.sheet("monitor", "Monitor outputs L and R")
    nx = refs(600)
    s.note("DAC 1 (L) and DAC 2 (R). MFB per leg: R1 5.1k, R2 11k, R3 360R, C1 6.8n, C2 330p: "
           "gain 2.157 (+17.9 dBu at 0 dBFS), f0 53.4 kHz, Q 0.74 (architecture 3.2).")
    s.note("Relay off (the default): NC grounds the jack side of each leg. Coil low side to the "
           "driver on the mute sheet.")
    for dac, side in ((1, "L"), (2, "R")):
        hot, cold = out_channel(s, nx, f"MON_{side}", dac, f"RLY_MON_{side}")
        s.part(JACK, nx("J"), "NMJ6HCD2", JACK_FP, {"T": hot, "R": cold, "S": "CHASSIS"},
               nc=["TN", "RN", "SN"], fields=HAND)
        s.row()
    rail_bulk(s, nx)


def sheet_line34(b):
    s = b.sheet("line34", "Line outputs 3 and 4")
    nx = refs(700)
    s.note("DAC 5 (line 3) and DAC 6 (line 4): the monitor stages and relays, to the J_LINE34 "
           "header instead of jacks (rev_a_board_split.md 2, default 1).")
    s.note("J_LINE34: 1, 2 line 3 hot, cold; 5, 6 line 4 hot, cold; 3, 4, 7, 8 GND; 9, 10 "
           "CHASSIS for a jack board's sleeves.")
    nets = {}
    for dac, ch in ((5, 3), (6, 4)):
        nets[ch] = out_channel(s, nx, f"LINE{ch}", dac, f"RLY_LINE{ch}")
    s.part("Connector_Generic:Conn_02x05_Odd_Even", nx("J"), "J_LINE34",
           "Connector_IDC:IDC-Header_2x05_P2.54mm_Vertical",
           {"1": nets[3][0], "2": nets[3][1], "3": "GND", "4": "GND",
            "5": nets[4][0], "6": nets[4][1], "7": "GND", "8": "GND",
            "9": "CHASSIS", "10": "CHASSIS"}, fields=HAND)
    s.row()
    rail_bulk(s, nx)


# ---------------------------------------------------------------- 8. headphones

def sheet_phones(b):
    s = b.sheet("phones", "Headphone amplifier")
    nx = refs(800)
    s.note("DAC 3 (L) and DAC 4 (R), AC-coupled into an OPA1622 difference amplifier: Rin 10.0k, "
           "Rf = Rg = 2.43k, G = 0.243 (0.687 V rms at 0 dBFS), 1R build-out (architecture 3, 12).")
    s.note("HP_L_RET and HP_R_RET join GND only through NT801 and NT802, placed at U801's GND "
           "pin with Rg's ground: the returns' single point (rev_a_board_split.md 3.4).")
    u = "U801"
    for ch, dac, unit, (pp, pm, po) in (("L", 3, 1, ("1", "10", "9")),
                                         ("R", 4, 2, ("5", "6", "7"))):
        n = f"HP{ch}"
        s.cp(nx("C"), "10u 16V", f"DAC{dac}_P", n + "_P_AC", CP4)
        s.r(nx("R"), "10.0k", n + "_P_AC", n + "_NI")
        s.r(nx("R"), "2.43k", n + "_NI", "GND")
        s.c(nx("C"), "680p 50V C0G", n + "_NI", "GND")
        s.cp(nx("C"), "10u 16V", f"DAC{dac}_N", n + "_N_AC", CP4)
        s.r(nx("R"), "10.0k", n + "_N_AC", n + "_INV")
        s.r(nx("R"), "2.43k", n + "_INV", n + "_OUT")
        s.c(nx("C"), "680p 50V C0G", n + "_INV", n + "_OUT")
        conns = {pp: n + "_NI", pm: n + "_INV", po: n + "_OUT"}
        if unit == 1:
            conns["8"] = "HP_EN_GATED"
        s.part("Amplifier_Audio:OPA1622", u, "OPA1622IDRCR", "Package_SON:Texas_S-PVSON-N10",
               conns, unit=unit)
        s.r(nx("R"), "1R", n + "_OUT", f"HP_{ch}")
        s.row()
    # V- names both pin 4 and the thermal pad (pin 11): SBOS727B, pad to V-.
    s.part("Amplifier_Audio:OPA1622", u, "OPA1622IDRCR", "Package_SON:Texas_S-PVSON-N10",
           {"V+": "+12V_ANA", "V-": "-12V_ANA", "GND": "GND"}, unit=3)
    s.c(nx("C"), "100n 50V", "+12V_ANA", "GND")
    s.c(nx("C"), "100n 50V", "-12V_ANA", "GND")
    rail_bulk(s, nx)
    s.row()
    s.part("Device:NetTie_2", "NT801", "NetTie_2", "NetTie:NetTie-2_SMD_Pad0.5mm",
           {"1": "HP_L_RET", "2": "GND"})
    s.part("Device:NetTie_2", "NT802", "NetTie_2", "NetTie:NetTie-2_SMD_Pad0.5mm",
           {"1": "HP_R_RET", "2": "GND"})
    pins, nc = links.pins("J_HP")
    s.part("Connector_Generic:Conn_02x03_Odd_Even", "J801", "J_HP",
           "Connector_IDC:IDC-Header_2x03_P2.54mm_Vertical", pins, nc=nc, fields=HAND)


# ---------------------------------------------------------------- 9. mute

def sheet_mute(b):
    s = b.sheet("mute", "Mute and relay drivers")
    nx = refs(900)
    s.note("RAILS_OK low forces every relay off and the OPA1622 into shutdown, whatever the MCU "
           "does (architecture 8): each control line is ANDed with RAILS_OK.")
    s.note("100k pull-downs hold the gate drives low while 3V3_A ramps. Coil clamp: diode plus "
           "10 V zener to 5V_DIG (drain about 16 V), so release stays near the 3 ms figure.")
    s.part("74xGxx:74LVC2G08", "U901", "74LVC2G08DCTR", SSOP8,
           {"1": "MUTE_MON", "2": "RAILS_OK", "7": "MON_ON"})
    s.part("74xGxx:74LVC2G08", "U901", "74LVC2G08DCTR", SSOP8,
           {"5": "MUTE_LINE34", "6": "RAILS_OK", "3": "LINE34_ON"}, unit=2)
    s.part("74xGxx:74LVC2G08", "U901", "74LVC2G08DCTR", SSOP8, {"8": "3V3_A", "4": "GND"},
           unit=3)
    s.c(nx("C"), "100n", "3V3_A", "GND")
    s.part("74xGxx:74LVC1G08", "U902", "74LVC1G08DBVR", SOT235,
           {"1": "HP_EN", "2": "RAILS_OK", "4": "HP_EN_GATED", "5": "3V3_A", "3": "GND"})
    s.c(nx("C"), "100n", "3V3_A", "GND")
    for net in ("MON_ON", "LINE34_ON", "HP_EN_GATED"):
        s.r(nx("R"), "100k", net, "GND")
    s.row()
    for gate, clamp, coils in (("MON_ON", "MON_CLAMP", ("RLY_MON_L", "RLY_MON_R")),
                               ("LINE34_ON", "LINE34_CLAMP", ("RLY_LINE3", "RLY_LINE4"))):
        for coil in coils:
            s.part("Transistor_FET:BSS138", nx("Q"), "BSS138", SOT23,
                   {"G": gate, "S": "GND", "D": coil})
            s.part("Device:D", nx("D"), "1N4148W", SOD123, {"A": coil, "K": clamp})
        s.part("Device:D_Zener", nx("D"), "BZT52C10 (10V)", SOD123, {"K": clamp, "A": "5V_DIG"})
        s.row()


# ---------------------------------------------------------------- 10. mechanical and test

TEST_POINTS = [
    # Rails (architecture 14): the arriving rails and each regulator's output before its link.
    ("+15V_RAW", TP_RAIL), ("-15V_RAW", TP_RAIL), ("5V5_PRE", TP_RAIL), ("5V_DIG", TP_RAIL),
    ("+12V_ANA_REG", TP_RAIL), ("-12V_ANA_REG", TP_RAIL), ("5V_ANA_REG", TP_RAIL),
    ("3V3_A_REG", TP_RAIL), ("GND", TP_RAIL), ("GND", TP_RAIL),
    None,
    # Clocks.
    ("OSC_24M", TP_SIG), ("OSC_22M", TP_SIG), ("MCLK_MUX", TP_SIG), ("SCKI", TP_SIG),
    ("MCLK_MCU", TP_SIG),
    None,
    # TDM and control.
    ("BCK", TP_SIG), ("LRCK", TP_SIG), ("DIN1", TP_SIG), ("DOUT1", TP_SIG),
    ("CODEC_DOUT2", TP_SIG), ("CODEC_DIN2", TP_SIG), ("I2C1_SCL", TP_SIG), ("I2C1_SDA", TP_SIG),
    ("CODEC_RST_N", TP_SIG), ("CODEC_OVF", TP_SIG), ("CODEC_MODE", TP_SIG),
    None,
    # Mute and power.
    ("RAILS_OK", TP_SIG), ("RLY_MON_L", TP_SIG), ("RLY_MON_R", TP_SIG), ("RLY_LINE3", TP_SIG),
    ("RLY_LINE4", TP_SIG), ("HP_EN_GATED", TP_SIG),
    None,
    # Analogue: DAC pins used, stage outputs before the relays, ADC inputs, headphones.
] + [(f"DAC{d}_{p}", TP_SIG) for d in range(1, 7) for p in "PN"] + [None] + [
    (f"{ch}_{leg}_OUT", TP_SIG) for ch in ("MON_L", "MON_R", "LINE3", "LINE4") for leg in "HC"
] + [None] + [(f"ADC{c}_{p}", TP_SIG) for c in (1, 2) for p in "PN"] + [
    ("HP_L", TP_SIG), ("HP_R", TP_SIG)]


def sheet_mech(b):
    s = b.sheet("mech", "Mechanical and test points")
    nx = refs(1000)
    s.note("CHASSIS is the chassis strip along the rear edge: jack sleeves and the jacks' RF and "
           "TVS parts. It meets the case at MH1 (near the jacks) only; circuit GND meets the "
           "chassis at D's bond hole only (architecture 7). MH2 to MH4: insulating standoffs.")
    s.part("Mechanical:MountingHole_Pad", "MH1", "M3 to CHASSIS",
           "MountingHole:MountingHole_3.2mm_M3_Pad_Via", {"1": "CHASSIS"})
    for i in (2, 3, 4):
        s.part("Mechanical:MountingHole", f"MH{i}", "M3 insulated",
               "MountingHole:MountingHole_3.2mm_M3", {})
    s.flag("CHASSIS")  # Bonded through MH1 and the case; nothing on A drives it.
    s.row()
    n = 0
    for tp in TEST_POINTS:
        if tp is None:
            s.row()
            continue
        net, fp = tp
        n += 1
        s.part("Connector:TestPoint", f"TP{1000 + n}", net, fp, {"1": net})


# ---------------------------------------------------------------- main

def main():
    b = Board("rev_a_a", "Rev A board A: converter and analogue", HERE)
    for net in RAILS:
        b.rail(net)
    for make in (sheet_link, sheet_power, sheet_clocks, sheet_converter, sheet_inputs,
                 sheet_monitor, sheet_line34, sheet_phones, sheet_mute, sheet_mech):
        make(b)
    b.write()
    found = b.erc()
    for v in found:
        print(v)
    errors = [v for v in found if v.startswith("error")]
    print(f"ERC: {len(errors)} errors, {len(found) - len(errors)} warnings")
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
