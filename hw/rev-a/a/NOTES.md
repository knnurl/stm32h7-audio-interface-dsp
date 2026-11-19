# Board A, converter and analogue: schematic notes (batch 5, stage 3)

2026-11-19. `design.py` here is the source of truth until the owner signs off the schematic
review (`hw/README.md`). Regenerate with `python hw/rev-a/a/design.py` from the repo root; it
writes `rev_a_a.kicad_pro` and eleven sheets, runs KiCad's ERC and exits non-zero on any error.

Sources: `docs/notes/rev_a_architecture.md` (cited "arch"), `rev_a_input_budget.md`,
`rev_a_board_split.md`, `part_selection.md`; datasheets SBAS452A (PCM3168A), SBOS727B (OPA1622),
SBOS855E (OPA1678), SBVS121E (TPS7A49), SBVS125D (TPS7A30), SBVS338H (TPS7A20), SCES416N
(SN74LVC1G97, fetched from ti.com for this stage), Omron G6K datasheet.

## ERC

**0 errors, 0 warnings** (`kicad-cli sch erc --severity-all`, KiCad 10.0.8).

PWR_FLAGs, and why each is honest:
- `GND`, `5V_DIG`, `5V5_PRE`, `+15V_RAW`, `-15V_RAW`: arrive over J_LINK (link sheet).
- `+12V_ANA`, `-12V_ANA`, `5V_ANA`, `3V3_A`: driven by their regulators through the 0 ohm
  bring-up links; ERC does not see through a resistor.
- `5V5_LC`, `5V5_RC`, `OSC_24M_VDD`, `OSC_22M_VDD`: fed through an inductor, a resistor or a
  ferrite, same reason.
- `CHASSIS`: nothing on A drives it; it is bonded to the case through MH1.

Cable check: KiCad's netlist of this board, J101 (Value `J_LINK`) and J801 (Value `J_HP`),
compared pin by pin against `hw/tools/links.py`: **0 differences**. `check_links.py` as a whole
needs board D's netlist too and is run once D is drawn.

## Sheets and part counts (328 parts)

| Sheet | Parts | Content |
|---|---|---|
| 1 Link to board D | 8 | J_LINK, control-line pulls, 5V_DIG bulk |
| 2 Linear regulators | 28 | TPS7A4901, TPS7A3001, TPS7A2050, TPS7A2033, filters, links |
| 3 Clocks | 18 | two oscillators, 74LVC1G97 mux, 74LVC2G34 buffer |
| 4 Converter PCM3168A | 26 | converter, straps, terminations, decoupling |
| 5 Line inputs 1 and 2 | 48 | two jacks, four input legs |
| 6 Monitor outputs L and R | 48 | four output legs, two relays, two jacks |
| 7 Line outputs 3 and 4 | 47 | four output legs, two relays, J_LINE34 |
| 8 Headphone amplifier | 26 | OPA1622, net ties, J_HP |
| 9 Mute and relay drivers | 17 | AND gates, four BSS138, coil clamps |
| 10 Mechanical and test points | 62 | four mounting holes, 58 test points |

Reference designators are numbered by sheet: 1xx link, 2xx power, ... 9xx mute, 10xx test.

## 1. Link (sheet `link`)

- J101 `J_LINK`: `Connector_Generic:Conn_02x20_Odd_Even`, footprint
  `Connector_IDC:IDC-Header_2x20_P2.54mm_Vertical` (shrouded box header), pins from
  `links.pins("J_LINK")`. Fit by hand.
- Pull-downs 10k to GND on `CODEC_RST_N`, `MUTE_MON`, `MUTE_LINE34`, `HP_EN`, `OSC_22M_EN`;
  pull-up 10k to 3V3_A on `OSC_SEL` (arch 8, pin_plan.md). An unplugged cable or a reset MCU
  (pins high-impedance) gives: converter in reset, relays off, OPA1622 shut down, 24.576 MHz
  selected. 10k against a push-pull GPIO costs 0.33 mA when high. Layout: each next to the part
  it controls (split note 3.1).
- No I2C pull-ups on A (2.2k on D, to the Nucleo 3V3). `RAILS_OK` arrives open-drain, pulled up
  on D with a hysteresis resistor; board D asks for no load under 100k on it. On A it has none:
  only three LVC gate inputs (leakage of a few uA at most) and a test point, no pull resistor.
- Series 33 ohm only at A's drivers: DOUT1 (R405, converter sheet) and MCLK_MCU (R306, clocks
  sheet). BCK, LRCK, DIN1 have theirs on D.
- C101 10u on 5V_DIG at the connector: local charge for the relay coils' switching current.

## 2. Power (sheet `power`)

Every regulator output reaches its rail through a 0 ohm link (R206, R212, R214, R217), open for
bring-up unloaded (arch 14). Each regulator's output cap and feedback network sit before the link
so it is stable unloaded. Test points are on the regulator side (`*_REG`).

### +12V_ANA: TPS7A4901 (U201)
- Custom symbol `rev_a:TPS7A4901` checked against SBVS121E Pin Functions: OUT 1, FB 2, NC 3,
  GND 4, EN 5, NR/SS 6, DNC 7, IN 8, PowerPAD (open or GND; tied to GND). NC and DNC left open
  (DNC: "do not route to any net").
- Feedback (9.1.1, Eq. 2): R1 = R2 (VOUT / VFB - 1). VFB 1.194 V ("adjustable output 1.194 V to
  33 V", features) [Verify: the electrical table is garbled in the extraction]. R2 = 10.0k, R1 =
  90.9k (E96): VOUT = 1.194 x 10.09 = **12.05 V**. Divider current 119 uA, over the 5 uA minimum.
- CFF 10 nF across R1 and CNR/SS 10 nF (9.1.4, Figure 29, "highly recommends 10 nF"). Soft start
  tSS = 1.4 ms/nF x 10 nF = 14 ms (Eq. 1).
- EN tied to IN (Pin Functions: "can be connected to IN, if not used").
- Input 10u 25V X7R (9.1.3: 2.2 uF minimum, 10 uF recommended) plus **100u 25V electrolytic**
  for hold-up (below). Output 10u 25V X7R. Ratings: 1.5 x 15 V = 22.5 V, so 25 V.

### -12V_ANA: TPS7A3001 (U202)
- `rev_a:TPS7A3001` checked against SBVS125D Pin Functions: same numbering as the TPS7A49.
- R1 93.1k, R2 10.0k: SBVS125D Table 2 ("standard 1 % values", -12 V). With the typical VREF
  of -1.176 V this gives -12.12 V; the table implies an effective 1.164 V [Verify on the bench].
- CFF and CNR/SS 10 nF as for U201 [Verify: SBVS125D's soft-start equation not re-read; assumed
  the same order, about 14 ms]. Review m13: SBVS125D Eq. 1 gives 0.9 ms/nF, so **9 ms**. EN tied to IN (Pin Functions). Caps as U201, electrolytic with
  its + to GND.

### Hold-up and the raw rails' capacitance (arch 5.3 and 8; board D's constraint)
The WRA module allows at most 220 uF of load per output. Board D has 110 uF per rail after its
output LC, so **board A keeps each raw rail at 110 uF or less**, and it has exactly that:

| Rail | On A | Parts |
|---|---|---|
| +15V_RAW | 110 uF | C201 100u 25V electrolytic, C202 10u 25V X7R (U201's input caps) |
| -15V_RAW | 110 uF | C206 100u 25V electrolytic, C207 10u 25V X7R (U202's input caps) |

Nothing else on A sits on the raw rails (every op-amp decouples on +/-12V_ANA, after the LDOs).
Total 220 uF per rail. Board D's hold-up figure is now about **5 ms** at the worst load before
the 15 V rails fall below the LDOs' minimum input, against the relay's 3 ms release (arch 8):
about 2 ms of margin, less than the architecture's 5 ms; bring-up step 4 measures it, with the
coil clamp of section 9 keeping the release near 3 ms.

LDO dissipation at 90.5 mA: (15 - 12) x 0.0905 = 0.27 W each (arch 5.3) [Verify the HVSSOP
thermal figure in stage 4].

### 5V_ANA: TPS7A2050 (U203), SOT-23-5 (DBV)
- Stock symbol `Regulator_Linear:TPS7A20xxxDBV`, footprint SOT-23-5; SBVS338H pin table for DBV:
  IN 1, GND 2, EN 3, N/C 4, OUT 5. Pin 4 left open. EN tied to IN (smart enable, 500k internal
  pull-down otherwise holds it off).
- LC filter from arch 5.2: L201 2.2 uH (1210), C207 22u 10V. Corner 1 / (2 pi sqrt(2.2 uH x
  22 uF)) = 22.9 kHz, about -56 dB at the buck's 580 kHz. Characteristic impedance 0.32 ohm; with
  about 0.1 ohm of inductor DCR the peak at 23 kHz is about Q = 3 (+10 dB), which the LDO's
  PSRR (about 70 dB there) covers. A damping electrolytic can be added in layout if the bench
  shows ringing [Verify the inductor part, its DCR and saturation at 0.21 A].
- Output 10u 16V X7R (SBVS338H: effective 0.47 to 200 uF, ESR under 100 mohm). The converter's
  4 x (1u + 10u) on 5V_ANA bring the total to about 54 uF, inside the 200 uF maximum.
- **DBV rather than DQN.** The architecture's only reason for the 1 x 1 mm X2SON was LCSC stock
  (the DBV was not found there). Electrically DBV is the better choice: rework by hand,
  dropout 145 mV against 140 mV (still 0.37 V of headroom from 5.5 V - 2 %), similar thermal
  resistance. **Correction to arch 5.2:** it quoted 54.4 C/W for the SOT-23-5; in SBVS338H's
  thermal table that figure reads as RthJB. RthJA is **187.1 C/W** for DBV and 166.1 C/W for DQN
  [Verify: the table is garbled in the text extraction]. So 0.11 W gives about +21 C, not +6 C.
  Fine either way. Sourcing of `TPS7A2050PDBVR` at JLC stays open (owner, V21).

### 3V3_A: TPS7A2033 (U204), SOT-23-5, with a 4.7 ohm series resistor
- Load: PCM3168A VDD 130 mA maximum (SBAS452A 8.5), two oscillators (one running) about 10 mA
  [Verify], logic under 1 mA: about 150 mA maximum.
- Straight from 5.5 V the LDO would burn (5.5 - 3.3) x 0.15 = 0.33 W, +62 C at 187 C/W.
  **Deviation:** R215 4.7 ohm (1206) ahead of it drops 0.71 V at 150 mA and takes 0.11 W (1206
  rated 0.25 W); the LDO then burns 0.22 W, +42 C. Input headroom at the buck's minimum
  (5.39 V): 5.39 - 0.71 - 3.3 = 1.38 V, far over the 145 mV dropout. R215 with C216 (10u) is
  also an RC filter at 3.4 kHz on the buck's ripple, about -45 dB at 580 kHz. The owner may
  replace it with 0 ohm.
- Caps as U203. EN tied to IN.
- SBAS452A 12.1.1 recommends VCC and VDD from one common source and switched on together: both
  LDOs start from 5V5_PRE in about 1 ms (SBVS338H tSTR 750 to 1150 us).

## 3. Clocks (sheet `clocks`)

- X301 24.576 MHz, X302 22.5792 MHz: stock `Oscillator:ASE-xxxMHz` (pin 1 EN, 2 GND, 3 OUT,
  4 Vdd), footprint `Oscillator_SMD_Abracon_ASE-4Pin_3.2x2.5mm`, the standard 3225 4-pad land
  of the YXC parts proposed in part_selection.md (O9322524576MEDA4SI and its 22.5792 MHz
  sibling) [Verify V22: pin 1 is OE active high, phase jitter under 45 ps rms, part numbers].
- Each fed from 3V3_A through a ferrite (600 ohm at 100 MHz, 0603) and 10 uF plus 100 nF
  (board split 1, arch 1).
- OE: X301 on `OSC_SEL`, X302 on `OSC_22M_EN` (pin_plan.md: "OSC_SEL: 24.576 MHz OE and mux
  select (pull-up)"). **OSC_SEL high selects 24.576 MHz**, matching arch 8 step 1 (the
  oscillator "selected by its pull-up (24.576 MHz) runs").
- 33 ohm at each oscillator output (#78, part_selection.md: "33 ohm series resistor at each
  source").
- **100k pull-down on each oscillator output (after its 33 ohm), not in the architecture:** a
  disabled oscillator's output goes high-impedance [Verify for the chosen part], which would
  leave a mux input floating. 100k loads a 24 MHz CMOS output by nothing measurable.
- **Mux, part change:** **74LVC1G97** (`74xGxx:74LVC1G97`, SOT-23-6 DBV) configured as a 2:1
  multiplexer replaces the 74LVC1G157 of stage 2, because KiCad has no symbol for the 157 and its
  pin table could not be read. SCES416N Function Table: In2 low gives Y = In1, In2 high gives
  Y = In0; DBV pins In1 1, GND 2, In0 3, Y 4, VCC 5, In2 6 (checked against the KiCad symbol).
  So In2 = OSC_SEL, In0 = OSC_24M, In1 = OSC_22M.
- Buffer 74LVC2G34 (DBV, SOT-23-6: 1A 1, GND 2, 2A 3, 2Y 4, VCC 5, 1Y 6), both inputs from the
  mux, each output through 33 ohm: `SCKI` to the converter, `MCLK_MCU` to J_LINK pin 2.
- 100 nF on each logic VCC. All on 3V3_A.
- Rate change switching (arch 8): enable the other oscillator, switch OSC_SEL, disable the
  first. Note OSC_SEL drives both the 24.576 MHz OE and the select, so with OSC_SEL low the
  24.576 MHz is off by hardware; the firmware raises OSC_22M_EN before lowering OSC_SEL.

## 4. Converter (sheet `converter`)

- U401 `rev_a:PCM3168A`: every pin number checked against SBAS452A Pin Functions (pins 1 to 64)
  and the pin diagram; PowerPAD as pin 65 to GND (12.1.11).
- **Control mode:** MODE (pin 48) to DGND gives I2C. SBAS452A's pin table states it in text
  ("Tied to VDD: SPI, pull-up: H/W single-ended input, pull-down: H/W and differential input,
  tied to DGND: I2C"), which settles the [Verify] of arch 1 (Table 6 was garbled). MODE goes to
  GND through R401 0 ohm so the strap has a test point and can be changed to the 220k of
  Figure 57 without a cut. MODE is sampled at power-on or a rising RST, with SCKI present (9.4.1).
- **I2C address 0x44:** 7-bit address 1 0 0 0 1 ADR1 ADR0 (9.3.14, Figure 43); ADR1 = ADR0 = 0
  gives 0b1000100 = 0x44. MS/ADR0 (45) and MDO/ADR1 (44) to GND through 10k each rather than
  directly: pin 44 is a tri-state output in SPI mode, so a misread MODE never shorts it. The pin
  table's pull-down column for these two pins is garbled; external pull-downs make it moot.
- SCL pin 42, SDA pin 43 to `I2C1_SCL`, `I2C1_SDA` (pull-ups on D).
- RST (4) on `CODEC_RST_N` (10k pull-down on the link sheet; the pin also has an internal
  pull-down per the pin table). OVF (5) to `CODEC_OVF` (reset-done pulse, 9.4.1).
- BCKAD and BCKDA tied to `BCK`, LRCKAD and LRCKDA to `LRCK` (arch 2, pin_plan.md). DIN1 from
  the link; DOUT1 through R405 33 ohm to the link (12.2: 22 to 100 ohm on the audio lines).
- DIN2: 10k to DGND and a test pad (arch 15). DIN3, DIN4: to DGND (inputs without pull-down,
  pin table). DOUT2: test pad only. DOUT3, ZERO: open (outputs).
- **Unused ADCs 3 to 6:** 12.1.3's second method, for channels left in differential mode (the
  default): + and - joined and 100 nF to AGNDAD per channel (range 1 nF to 1 uF).
- **Unused DACs 7 and 8:** outputs left open [Verify: SBAS452A says nothing on unused DAC
  outputs; open is the usual practice, and their power-save is by register].
- **Decoupling:** per supply pin (VCCAD1 49, VCCAD2 3, VCCDA1 14, VCCDA2 34, VDD1 46, VDD2 12)
  1u 16V X7R at the pin plus 10u 16V electrolytic (12.1.1); each cap has a `Near` field naming
  its pin. VCOMAD, VCOMDA, VREFAD1, VREFAD2: 10u 16V electrolytic each, + to the pin (12.1.4,
  12.1.5). Rating: 1.5 x 5 V = 7.5 V, so 16 V. Electrolytic as the datasheet asks, also
  avoiding ceramic voltage coefficient on the references.
- All grounds (AGNDAD1/2, AGNDDA1/2, DGND1/2, PowerPAD) on GND: one plane, joined under the
  part (12.1.2).
- Footprint: the symbol's `Texas_TQFP-64-1EP_10x10mm_P0.5mm_EP8x8mm` is a placeholder; SBAS452A
  gives a 7.25 x 7.00 mm PowerPAD [Verify the PAP0064 land pattern in stage 4].

## 5. Line inputs 1 and 2 (sheet `inputs`)

Per leg, as EX5 and `rev_a_input_budget.md`, protection from arch 9:

| Part | Value | Why |
|---|---|---|
| Series R | 100R | RF filter with the shunt cap (arch 9, #78) |
| Shunt C to CHASSIS | 470p 50V C0G | 1 / (2 pi x (100 + 100 source) x 470p) = 1.7 MHz; 480 kHz from a 600 ohm source |
| TVS to CHASSIS | bidirectional, 15 V stand-off | arch 9: a +20 dBu unbalanced signal peaks at 10.96 V |
| Bleed to GND | 1M | DC reference for the coupling cap's source side, so plugging in does not thump (#78's "high-value resistor"). Input impedance 20k parallel 1M = 19.6k per leg (budget: 20k) |
| Coupling C | 10u 35V electrolytic, + to the op-amp side | holds 2.5 V (VCOMAD); HPF 1 / (2 pi x 20k x 10u) = 0.8 Hz. 35 V covers the TVS clamping voltage, not only the 15 V stand-off [Verify the TVS clamp] |
| Rin | 20.0k 0.1 % | budget 1; CMRR 48 dB worst case with 0.1 % (budget 5) |
| Rf | 5.11k 0.1 % | G = 0.2555, 0 dBFS = +20.1 dBu |
| Cf across Rf | 100p C0G | stage corner 1 / (2 pi x 5.11k x 100p) = 311 kHz, above the ADC filter [Verify: my value, not from a source] |
| Op-amp | OPA1678 (one dual per channel) | + input on VCOMAD, so the output sits at 2.5 V |
| ADC series R | 47R | SBAS452A 12.1.3 example |
| ADC differential C | 10n 50V C0G (0805), across VINx+ and VINx- | 1 / (2 pi x 94 ohm x 10n) = 169 kHz, the 12.1.3 corner of 160 kHz. The extraction reads "47 ohm and 0.1 uF to 470 ohm and 0.001 uF"; only 0.01 uF matches the 470 ohm / 1 nF pair and the stated corner [Verify in the PDF]. C0G: 12.1.3 asks for a film or a high-voltage ceramic for THD |

- Hot leg (tip) drives VINx-, cold leg (ring) VINx+: the stage inverts, so the channel's
  polarity is kept.
- VCOMAD feeds the four + inputs directly: CMOS inputs draw pA, so its 10 uF and internal
  source impedance are not loaded.
- Jacks NMJ6HCD2: T hot, R cold, S to CHASSIS; switch contacts TN, RN, SN unused.
- Op-amp decoupling 100n per rail per package, 10u per rail per sheet.

## 6. Monitor outputs L and R (sheet `monitor`)

Per leg: AC coupling, MFB low-pass, build-out, relay, bleed, TVS.

- **Gain** -R2/R1 = -11k / 5.1k = -2.157 (arch 3.2): 2.828 V rms differential from the DAC
  becomes 6.100 V rms = +17.9 dBu.
- **Filter capacitors (stage 3's task in arch 3.2).** MFB: w0 = 1 / sqrt(R2 R3 C1 C2),
  Q = sqrt(R2 R3 C1 C2) / (C2 (R2 + R3 + R2 R3 / R1)), with R1 5.1k, R2 11k, R3 360R
  (R2 + R3 + R2 R3 / R1 = 12.14k). For Q 0.707 at 55 kHz: C2 = 337 pF, C1 = 6.27 nF. Chosen
  **C1 6.8n, C2 330p (C0G)**: f0 = 53.4 kHz, Q = 0.744 (TI's examples 53 to 54 kHz, SBAS452A
  Figures 61, 62). Response at 20 kHz: +0.03 dB. C1 from the summing node to GND, C2 from the
  output to the inverting input; + input to GND.
- **AC coupling:** 22u 16V electrolytic, + to the DAC (2.5 V DC); with R1 = 5.1k the corner is
  1.4 Hz. The DAC sees R1 at least, over the 5 k minimum when AC-coupled (SBAS452A 8.5 note 11).
- VOUTx- feeds the hot leg, VOUTx+ the cold leg (the stage inverts).
- **Build-out** 100R per leg (arch 9).
- **Relay** K601, K602: Omron G6K-2F-Y DC5, stock `Relay:Omron_G6K-2` with footprint
  `Relay_SMD:Relay_DPDT_Omron_G6K-2F-Y` (pads 11, 12, 14, 21, 22, 24, A1, A2 match the symbol).
  In the symbol 11 is the common and rests on 12 (NC); 14 is NO. Wiring: COM to the jack side,
  NO to the stage (after 100R), NC to GND. Unpowered, each jack leg is grounded (arch 8).
  Coil A1 to 5V_DIG, A2 to the driver [Verify coil polarity: the G6K is polarised ("check the
  coil polarity"), the datasheet's terminal drawing is an image; A1 sits at the footprint's pin 1
  corner, assumed +]. Contacts 1 A at 30 V DC, 100 mohm max (G6K ratings).
- **Bleed** 10k from each jack-side leg to GND (arch 9): defines the jack during the transfer.
- **TVS** at the jack side, to CHASSIS (arch 9).
- Jacks NMJ6HCD2, T hot, R cold, S CHASSIS.

## 7. Line outputs 3 and 4 (sheet `line34`)

- DAC 5 (line 3) and DAC 6 (line 4) (arch 2), the same stages as section 6.
- **Two relays (K701, K702), not one.** The split note counts "three relay coils" and the task
  said "a relay", but grounding each leg through an NC contact (arch 8) needs four poles for two
  balanced channels, so two DPDT relays; arch 5.4 counts four coils (84 mA) the same way. Both
  driven together from `LINE34_ON`.
- **J_LINE34** (Conn_02x05_Odd_Even, Value `J_LINE34`, shrouded IDC 2 x 5), split note default 1.
  Proposed pin-out: 1 LINE3_HOT, 2 LINE3_COLD, 3 GND, 4 GND, 5 LINE4_HOT, 6 LINE4_COLD, 7 GND,
  8 GND, 9 CHASSIS, 10 CHASSIS. Each pair is next to its grounds in a ribbon; pins 9 and 10 let a
  jack board put its sleeves on the chassis strip as the rear jacks do [owner decides].
- TVS to CHASSIS at the header (a jack board may add its own at the jacks).

## 8. Headphones (sheet `phones`)

- U801 OPA1622 (`Amplifier_Audio:OPA1622`, `Package_SON:Texas_S-PVSON-N10`). Pins checked
  against SBOS727B: +INA 1, V+ 2, GND 3, V- 4, +INB 5, -INB 6, OUTB 7, EN 8, OUTA 9, -INA 10,
  thermal pad to V- (the symbol's hidden pin 11 "V-", joined to -12V_ANA).
- Difference amplifier per channel (arch 3.2, 4.2): Rin 10.0k on both inputs, Rf 2.43k (output
  to - input), Rg 2.43k (+ input to GND): G = 0.243, 0.687 V rms single-ended at 0 dBFS. Output
  = 0.243 x (VOUTx+ - VOUTx-), so the DAC's polarity is kept.
- DAC load: - input 10k, + input 12.43k, both over the 6.0k that note 11 gives for G = 0.243.
- AC coupling 10u 16V electrolytic per input, + to the DAC: corners 1.6 Hz (- side) and 1.3 Hz
  (+ side); the mismatch affects CMRR only below a few Hz.
- 680p C0G across Rf and across Rg (matched, so CMRR holds): corner 1 / (2 pi x 2.43k x 680p) =
  96 kHz, takes the DAC's out-of-band noise off the headphone cable [Verify: my value].
  The OPA1622 is unity-gain stable (SBOS727B features); noise gain here 1.24.
- Build-out 1R per channel (arch 3.2, 9) to `HP_L`, `HP_R`.
- **Returns:** `HP_L_RET` and `HP_R_RET` keep their own names to J_HP pins 2 and 3 and join GND
  only through NT801 and NT802 (`Device:NetTie_2`). Layout: both net ties, Rg's ground and U801
  pin 3 at one point (split note 3.4, arch 7). J_HP pins 5 and 6 unconnected (links.py).
- EN (pin 8) on `HP_EN_GATED` from the mute sheet. EN thresholds 0.78 V off, 0.82 V on,
  referred to the GND pin (SBOS727B 7.3.3); a 3.3 V logic high is well inside the supplies. EN is
  never left floating (7.3.3): a 100k pull-down holds it low while 3V3_A ramps, as Figure 48's
  divider does.
- Decoupling 100n per rail at U801 plus 10u per rail.

## 9. Mute (sheet `mute`)

- **Gating (arch 8):** each control line is ANDed with `RAILS_OK` in hardware:
  U901 74LVC2G08 (DCT, SSOP-8): `MUTE_MON` and `MUTE_LINE34`; U902 74LVC1G08 (DBV): `HP_EN`.
  RAILS_OK low forces both relay groups off and the OPA1622 into shutdown whatever the MCU does.
  On 3V3_A; LVC inputs tolerate 5.5 V, so D's RAILS_OK pull-up may go to any rail up to 5 V.
  RAILS_OK has no pull resistor on A (board D: nothing under 100k on it).
  Why logic gates: a single part does the AND for all three outputs, defined levels, no analogue
  thresholds; a diode-OR to ground of the gate drives was the alternative but leaves the levels
  dependent on pull-up values.
- 100k pull-downs on `MON_ON`, `LINE34_ON` and `HP_EN_GATED`: while 3V3_A is below the gates'
  operating range the outputs are undefined; the pulls keep the MOSFETs off and EN low.
- **Drivers:** one BSS138 per coil (Q901 to Q904), low-side, gate straight from the gate output
  (relay speeds need no gate resistor). Coil 5 V / 237 ohm = 21.1 mA (G6K ratings).
  BSS138: VGS(th) 0.8 to 1.5 V, so 3.3 V of drive is ample for 21 mA [Verify RDS(on) at
  VGS = 3.3 V in the chosen maker's datasheet]. A JLC basic part [Verify].
- **Coil clamp, deviation from "flyback diodes":** each coil has a 1N4148W from its low side to a
  clamp node, and each relay pair one BZT52C10 (10 V zener) from that node to 5V_DIG. At turn-off
  the drain rises to 5 + 0.7 + 10 = 15.7 V (BSS138 rated 50 V) and the coil's energy decays fast.
  A plain diode clamps at 0.7 V and lengthens release well past the datasheet's 3 ms (which is
  measured without a diode), and the power-fail margin of arch 8 assumes 3 ms. While the coils
  are on, the zener conducts forward and the diodes are reverse-biased by about 4.3 V; harmless.
  The pair shares a zener because both relays always switch together [Verify the release time
  with the clamp at bring-up step 4].
- Coils on 5V_DIG, two link conductors, 84 mA for four coils.

## 10. Mechanical and test points (sheet `mech`)

- **CHASSIS** is the chassis strip along A's rear edge: jack sleeves, input RF caps, all
  input and output TVS. MH1 (`MountingHole_3.2mm_M3_Pad_Via`, near the jacks) bonds it to the
  case; MH2 to MH4 are non-plated M3 holes on insulating standoffs. Circuit GND meets the chassis
  only at D's bond hole (arch 7), so A has no GND to CHASSIS link. If the NMJ6HCD2 ferrules touch
  the sleeves, the rear panel bonds the strip at every jack as well, which is consistent
  (all on one edge) [Verify V28].
- **Test points** (arch 14, the ones on A), 58: rails `+15V_RAW`, `-15V_RAW`, `5V5_PRE`,
  `5V_DIG`, each regulator output before its link, two GND posts (1.5 mm pads); clocks
  `OSC_24M`, `OSC_22M`, `MCLK_MUX`, `SCKI`, `MCLK_MCU`; TDM and control `BCK`, `LRCK`, `DIN1`,
  `DOUT1`, `CODEC_DOUT2`, `CODEC_DIN2`, `I2C1_SCL`, `I2C1_SDA`, `CODEC_RST_N`, `CODEC_OVF`,
  `CODEC_MODE`; mute `RAILS_OK`, the four coil low sides, `HP_EN_GATED`; analogue: the twelve
  DAC pins used, the eight output stage outputs before the build-out, the four ADC input pins,
  `HP_L`, `HP_R` (1.0 mm pads). Each test point's Value is its net.

## Deviations from the architecture and the split note

1. 74LVC1G97 as a 2:1 mux instead of the 74LVC1G157 (no KiCad symbol for the 157).
2. Four relays (two for line 3/4) instead of the split note's three coils and the brief's "a
   relay": a pole per leg is needed for the NC grounding; arch 5.4 already counts four.
3. 4.7 ohm series resistor ahead of the TPS7A2033 (thermal; also an RC filter).
4. TPS7A2050 and TPS7A2033 in SOT-23-5 (DBV), not X2SON; and arch 5.2's 54.4 C/W for DBV
   corrected to 187.1 C/W (that figure is RthJB).
5. Coil clamp diode plus zener instead of a plain flyback diode (keeps the 3 ms release).
6. 33 ohm at each oscillator output (part_selection.md asked for it; arch 2 shows only the
   buffer's) and 100k pull-downs on the mux inputs.
7. 1M bleed on each input leg (input impedance 19.6k, not 20k).
8. ADR0, ADR1 through 10k, MODE through 0 ohm, instead of direct ties.
9. Input and output TVS referenced to CHASSIS (arch 9 does not say; arch 7 puts the jacks'
   protection parts on the strip).
10. Test points on each regulator's output before its link rather than on the rail.
11. Hold-up capacitance split: 110 uF per raw rail on A, 110 uF on D (D's constraint).

## [Verify] list

1. TPS7A49 VFB = 1.194 V typical (table garbled; features line used).
2. TPS7A30 -12 V divider: Table 2's 93.1k implies 1.164 V; expect -12.0 to -12.1 V.
3. TPS7A30 soft start with 10 nF: 9 ms (SBVS125D Eq. 1, review m13). Closed.
4. HVSSOP thermal resistance for 0.27 W per LDO (stage 4).
5. TPS7A20 thermal table reading (DBV RthJA 187.1 C/W) and DBV stock at LCSC/JLC (V21).
6. 3V3_A load: oscillator supply current about 10 mA.
7. 2.2 uH inductor part: DCR, saturation, and the LC's peaking on the bench.
8. Oscillators (V22): part numbers, pin 1 OE active high, output state when disabled, jitter.
9. Ferrite bead part (600 ohm at 100 MHz, 0603).
10. TVS part: `PESD15VL1BA` is a placeholder for "bidirectional, 15 V stand-off, low
    capacitance, SOD-323"; capacitance, clamp voltage and LCSC stock to confirm.
11. Input coupling cap: 35 V against the TVS clamp, and polarised versus bipolar.
12. Cf 100p (input stage) and 680p (headphones): my values.
13. SBAS452A 12.1.3 anti-aliasing values (0.01 uF reading).
14. Unused DAC 7, 8 outputs left open.
15. G6K coil polarity (A1 = +) and footprint pad mapping against Omron's terminal drawing.
16. Relay release time with the zener clamp (bring-up step 4).
17. BSS138 RDS(on) at VGS = 3.3 V; JLC class.
18. PCM3168A footprint against the PAP0064 land pattern (7.25 x 7.00 mm pad).
19. NMJ6HCD2 ferrule and sleeve contact (V28).
20. Hold-up margin: the review computes 6.7 ms, or 5.4 ms from the lowered RAILS_OK threshold
    (9.76 V), against a 3 ms release; measure at bring-up step 5.

## Open owner decisions

1. J_LINE34 pin-out, in particular CHASSIS on pins 9 and 10.
2. Two relays for line 3/4 (four coils in all).
3. SOT-23-5 for both TPS7A20 parts (rework, thermal) against the X2SON (LCSC stock), and the
   4.7 ohm ahead of the 3.3 V LDO.
4. The coil clamp zener.
5. Settled with board D: 110 uF per raw rail on each board, no load under 100k on RAILS_OK, no
   I2C pull-ups on A. RAILS_OK's pull-up rail must stay at 5.5 V or less (LVC inputs).

## Left for later stages

- Stage 4 placement notes carried in the schematic: per-pin decoupling (`Near` fields), the
  headphone ground point, pull-downs next to what they switch, no analogue traces on the bottom
  layer over the Nucleo's ST-LINK (split note 4).
- `check_links.py` once board D is drawn.
