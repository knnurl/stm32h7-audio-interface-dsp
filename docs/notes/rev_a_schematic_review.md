# Rev A schematic review (batch 5, stage 3)

**Date:** 2026-11-19.
**Reviewed:** commit `eda9585` ("hw: board A schematic (stage 3 draft)"), working tree clean:
`hw/rev-a/a/design.py`, `hw/rev-a/d/design.py`, `hw/rev-a/pl/design.py`, `hw/rev-a/pr/design.py`,
the KiCad projects they generate, each board's `NOTES.md`, `hw/tools/links.py`, and the intended
design in `rev_a_architecture.md`, `rev_a_board_split.md`, `pin_plan.md`, `rev_a_input_budget.md`.
**Reviewer:** Claude, who did not design these boards. No design file was edited.

**Method.**

1. Read each `design.py` in full and each `NOTES.md`, and checked the notes' claims against the
   netlist rather than taking them as given.
2. Exported KiCad's own netlist of every root sheet (`kicad-cli sch export netlist`) and dumped
   every part as pin number, pin name and net, so the connectivity checked is KiCad's, not the
   Python's.
3. Checked pin-outs against the datasheet text in the scratchpad (SBAS452A PCM3168A, SBOS727B
   OPA1622, SBOS855E OPA1678, SBVS338H TPS7A20, SBVS125D TPS7A30, SBVS121E TPS7A49, SLVSD90B
   TPS56320x, UM2408 Rev 6, Mornsun WRA_S-3WR2) and the stock footprints' pad names in KiCad 10's
   library.
4. Recomputed every gain, filter corner, divider, threshold and hold-up figure from the part
   values in the netlist.
5. Ran `hw/tools/check_links.py`: all four cables match `links.py` at both ends.

**How to read the evidence.** "Read" means taken from a datasheet or the netlist. "Computed"
means arithmetic on netlist values and datasheet figures. "Inferred" means engineering judgement
that no document here settles; those carry [Verify].

**Summary.** No connectivity error was found that would stop a board working: every pin-out that
could be checked against a datasheet is right, every polarised part is the right way round, every
divider gives its stated voltage, and every Nucleo pin matches the pin plan. Three major findings
need a schematic change before layout:

1. The over-voltage FET's soft-start does not limit inrush (M1).
2. The ADC inputs can be driven past the converter's pin limits (M2).
3. The supervisor's rising threshold leaves about 0.1 V of margin to a 12 V adapter (M3).

Four pin-outs and one relay mapping are unverified and would each cost a respin if wrong
(section 4).

## 1. Checklist verdicts

### 1.1 Decoupling per supply pin (value, placement intent, bulk)

| Board | Verdict | Evidence |
|---|---|---|
| A | pass | **PCM3168A:** 1 uF 16 V X7R plus 10 uF 16 V electrolytic on each of VCCAD1 (49), VCCAD2 (3), VCCDA1 (14), VCCDA2 (34), VDD1 (46), VDD2 (12), each with a `Near` field naming its pin (SBAS452A 12.1.1 asks for exactly this). **OPA1678 x 6, OPA1622:** 100 nF 50 V per rail per package, plus 10 uF 25 V X7R 1206 per rail per sheet. **Logic** (U301, U302, U901, U902): 100 nF each. **Oscillators:** ferrite, 10 uF and 100 nF each. **TPS7A4901, TPS7A3001:** 100 uF electrolytic plus 10 uF X7R in, 10 uF X7R out (SBVS121E 9.1.3: 2.2 uF minimum, 10 uF recommended). **TPS7A20s:** 22 uF or 10 uF in, 10 uF out. **Relay coils:** C101 10 uF on 5V_DIG. Placement intent is written down only for the converter (the `Near` fields); the op-amps' 100 nF have no `Near` field, so stage 4 must place them by hand. |
| D | pass, one note | **Bucks:** 2 x 10 uF 25 V plus 100 nF in, 2 x 22 uF 16 V out (SLVSD90B Table 7-2: 20 to 68 uF); VBST 100 nF. **Module:** C30 100 uF, L3 4.7 uH, C31 47 uF, C32/C34 10 uF 50 V, L4/L5 10 uH, C33/C35 100 uF 50 V (Mornsun Fig. 2). **TPS3808, TLV9001:** 100 nF each. **Nucleo:** C50 10 uF at 5V_EXT; C51 10 uF and C52 100 nF on NUCLEO_3V3. **PANEL_3V3:** FB80, then C83 10 uF and C84 100 nF. **USBLC6:** C60 1 uF on VBUS. **Optical** (DNP): 100 nF each [Verify the Toslink LC supply filter, batch 10]. Note: the total capacitance on 5V_DIG may exceed the buck's stated 68 uF (finding m12). |
| PL | pass | No ICs. C8 100 nF and C9 10 uF at the OLED header for the module. |
| PR | not applicable | No ICs: pots, switches and LEDs only. |

### 1.2 Reference pins

| Board | Verdict | Evidence |
|---|---|---|
| A | pass, two notes | **VCOMAD (1), VCOMDA (15), VREFAD1 (59), VREFAD2 (60):** 10 uF electrolytic each, + to the pin (12.1.4, 12.1.5). SBAS452A 8.5 gives VREFAD2's output voltage as AGNDAD1, so C on VREFAD2 sits unbiased at 0 V. That is harmless, and the right polarity for whatever small voltage appears. **VCOMAD** also biases the four input op-amps' + inputs. That is allowed by 9.3.3 ("can be used to bias external high-impedance circuits", 10 kohm output impedance, 1 uA allowable): the OPA1678's pA bias currents are far below it. The exception is when +/-12V_ANA is absent while 5V_ANA is up (finding m6). **TPS7A4901:** NR/SS 10 nF C0G, CFF 10 nF across R1, R1/R2 90.9k/10.0k: 1.194 x 10.09 = **12.05 V** (computed; VFB from the features line). **TPS7A3001:** NR/SS 10 nF, CFF 10 nF, 93.1k/10.0k: -1.176 x 10.31 = **-12.12 V** typical (computed; SBVS125D Table 2 lists exactly these values for -12 V). Divider currents of 119 and 117 uA are above the 5 uA minimum. **TPS7A20s:** fixed outputs, EN tied to IN. |
| D | pass, one issue | **Bucks:** VFB 768 mV typical, 749 to 787 mV (SLVSD90B 5.5); 54.9k/10k gives **4.98 V** (4.86 to 5.11 V), 61.9k/10k gives **5.52 V** (5.39 to 5.66 V), computed. Feedback is taken before the solder jumpers, so each buck regulates unloaded. **TL431 cut-off:** 53.6k/10k plus R5 1M gives a **15.70 V trip and 15.19 V release** (computed with Q2's gate 10 V below the source when on). **TPS3808:** 255k/10k plus R42 2.8M gives **10.47 V falling, 10.73 V rising** before the part's own hysteresis (computed). See finding M3. **Pot reference:** U8 TLV9001 follows VREFP (CN12-7, which is VDDA = VDD through R40, UM2408 Table 16), runs from 5V_DIG, and has dual feedback (R80 47 ohm, C82 1 uF, R81 10k, C81 330 nF). The R83 bypass is DNP. The topology is sound; its phase margin is not computed here [Verify by simulation, as D's notes say]. U8's input floats when the Nucleo is absent (finding m7). |
| PL, PR | pass | Every pot sits between POT_REF (pin 3) and POT_GND (pin 1), with its wiper 10 nF to POT_GND at the pot. POT_GND never joins GND on the panels. It meets GND only through the Nucleo's AGND pin (CN12-32). |

### 1.3 Clock termination

| Board | Verdict | Evidence |
|---|---|---|
| A | pass, one note | X301 24.576 MHz has its OE on OSC_SEL (10k pull-up to 3V3_A on A); X302 22.5792 MHz has its OE on OSC_22M_EN (10k pull-down). **The default is 24.576 MHz, selected and running**, with no MCU involvement, so SCKI is present before RST rises (SBAS452A 9.4.1 needs it to sample MODE). Each oscillator output has 33 ohm at the source and a 100k pull-down at the mux input, so a disabled (tri-stated) oscillator does not float the mux. **74LVC1G97** as a 2:1 mux: In0 = OSC_24M (pin 3), In1 = OSC_22M (pin 1), In2 = OSC_SEL (pin 6), Y pin 4. In2 high gives In0 (SCES416N function table as quoted in A's notes; it matches the netlist's pin names). **74LVC2G34** (1A 1, 2A 3, 2Y 4, 1Y 6): both inputs from the mux, 33 ohm at each output to SCKI and to MCLK_MCU (J_LINK pin 2). DOUT1 has 33 ohm at the converter. MCLK_MCU crosses about 60 mm of ribbon plus two board traces with only source termination (finding m9). |
| D | pass | R50, R51, R52 33 ohm at the MCU side of BCK, LRCK and DIN1, in series between the morpho pin and the ribbon. MCLK_MCU (to PC9) and DOUT1 (to PE3) arrive terminated from A. |
| PL, PR | not applicable | No clocks. |

### 1.4 Unused inputs and outputs

| Board | Verdict | Evidence |
|---|---|---|
| A | pass | **Op-amps:** all 12 OPA1678 sections and both OPA1622 sections are used. **ADC3 to ADC6:** + and - joined with 100 nF to GND. That is SBAS452A 12.1.3's second method, for channels in differential mode, and differential is the reset default (SEAD[6:1] = 00 0000, 9.5). **DACs 7, 8:** outputs open. The datasheet is silent on this; open outputs are normal practice [Verify]. **Data and flags:** DIN3 and DIN4 to GND; DIN2 10k to GND plus a pad; DOUT2 pad only; DOUT3 and ZERO open (outputs). **Regulators:** TPS7A20 pin 4 (N/C) open; TPS7A49/30 NC open, and DNC open as "do not route" requires. **Logic:** every LVC input is driven. **Jacks:** switch contacts open. **J_HP:** pins 5 and 6 open. |
| D | pass, one note | TPS3808 MR open (internal pull-up); WRA Ctrl open ("normal output when the Ctrl end is suspended", Design reference 3); USB SBU1/2 NC; J_PANEL pin 39 NC; every morpho pin outside the pin plan NC. The MCU inputs fed from A (PC9, PE3, PE12) have no pull resistor and float with J_LINK unplugged (finding m4). |
| PL | pass | OLED header pins 7 to 10 open (passive connector). Encoder and pot bracket pads (MP) are netless on purpose. |
| PR | pass | Jack switch contacts open. |

### 1.5 Power sequencing and power fail

| Board | Verdict | Evidence |
|---|---|---|
| A | pass | **Rails:** 5V_ANA and 3V3_A both come from 5V5_PRE through TPS7A20s with about 1 ms start (SBVS338H), so VCC and VDD rise together as SBAS452A 12.1.1 recommends. +12V_ANA soft-starts in 14 ms (1.4 ms/nF, SBVS121E Eq. 1) and -12V_ANA in **9 ms** (0.9 ms/nF, SBVS125D Eq. 1, not the 14 ms A's notes assume). **Default state is muted:** relays de-energised (NC grounds each jack leg, 10k bleed), OPA1622 EN low (100k pull-down after the gate), RST pulled down (10k plus the internal 50k). **RAILS_OK gating:** U901 (74LVC2G08) ANDs MUTE_MON and MUTE_LINE34 with RAILS_OK, and U902 (74LVC1G08) does the same for HP_EN, in hardware. 100k pull-downs hold the BSS138 gates and EN low while 3V3_A is below the gates' range. **Relay release against hold-up** (computed): with 12V_P's about 1.17 mF from 10.47 V to the module's 9 V minimum at 0.69 A, plus about 171 uF effective per raw rail (220 uF nominal with the ceramics derated) from 14.55 V to 12.3 V at 90.5 mA, the rails last **2.5 + 4.3 = 6.7 ms** against a 3 ms release. The coil clamp (1N4148W plus a 10 V zener to 5V_DIG, drain clamp 15.7 V against the BSS138's 50 V) keeps the release near the unclamped figure. **J_LINK unplugged:** A has no supply at all, so nothing on A can be in a wrong state. |
| D | issue | **Bucks:** enable above 5.1 V of 12V_P (100k/47k divider); 1 ms soft start. **RAILS_OK:** high 189 ms after 12V_P rises (C42 33 nF), open drain, pulled up to NUCLEO_3V3. Three issues: the inrush through Q2 (M1), the adapter margin (M3), and the dependence on NUCLEO_3V3 (m7). RAILS_OK watches 12V_P only (m6). **J_LINK unplugged:** live rails sit on J7's open pins and three MCU inputs float (m4). |
| PL, PR | pass | Passive: powered from PANEL_3V3 only. With J_PANEL unplugged, the pot inputs on D float (m3). |

### 1.6 Every net to a header pin against the pin plan

| Board | Verdict | Evidence |
|---|---|---|
| D | pass | All 62 signal nets on J2 (CN11) and J3 (CN12) were compared with `pin_plan.md` section 3 and with UM2408 Table 19 as extracted. Every one is on the pin the plan names, and each plan pin carries the port the table gives. For example: CN11-50 PE5 BCK, -48 PE4 LRCK, -62 PE6 DIN1, -47 PE3 DOUT1; CN12-1 PC9 MCLK; CN12-3/5 PB8/PB9 I2C1; CN11-40 PD3 RST; CN12-49 PE12 OVF; CN11-39/41/43 PD4/PD5/PD6; CN12-44/40/47 PE7/PE8/PE10; the seven pots on PA3, PC0, PA4, PA5, PA6, PB1, PF11; CN12-12/14 PA12/PA11; CN12-53 PE15. **GND:** CN11-8, 19, 20, 22, 49, 60 and CN12-9, 20, 39, 54, 63 all on GND. CN12-32 AGND is on POT_GND. **5V_EXT and JP2:** 5V_DIG reaches CN11-6 (5V_EXT) with C50; the sheet says JP2 must sit on 5-6 (UM2408 7.4.3). CN11-18 (5V), CN11-24 (VIN) and CN12-8 (5V_USB_STLK) are NC, so nothing back-feeds the Nucleo's 5 V. **BOOT0:** CN11-7 goes to a 2-pin header whose other pin is CN11-5 (3V3_VDD), the jumper position of Table 19 note 1. **Unverified:** CN12-14 is "PA11 or PE6". PE6 is DIN1 on CN11-62, so if the solder bridges were set the other way, USB D- would join the TDM data line [Verify V30 by continuity]. |
| A, PL, PR | not applicable | No Nucleo pins. All cable pin-outs match `links.py` at both ends (`check_links.py`, run for this review). |

## 2. The other checks

### 2.1 Gains and filter corners, computed from the netlist values

| Stage | Values | Computed | Architecture |
|---|---|---|---|
| Line input, per leg | Rin 20.0k, Rf 5.11k, Cf 100p, 47R + 10n differential | G = 0.2555, 0 dBFS = **+20.1 dBu** balanced; Cf pole 311 kHz; ADC RC 169 kHz; coupling HPF 0.8 Hz | +20 dBu (3.1); SBAS452A 12.1.3's 160 kHz |
| Monitor and line 3/4 MFB, per leg | R1 5.1k, R2 11k, R3 360R, C1 6.8n, C2 330p | G = -2.157, **+17.9 dBu**; f0 **53.4 kHz**, Q **0.744** | +17.9 dBu, about 55 kHz (3.2) |
| DAC load, MFB | R1 at a near-virtual-ground node | 5.1k against the 5k minimum, AC-coupled (8.5 note 11): 2 % margin, met with 1 % parts | met |
| Headphones | Rin 10.0k, Rf = Rg 2.43k, 680p across each, 1R build-out | G = 0.243, **0.687 V rms** at 0 dBFS; 96 kHz pole; DAC sees 10k and 12.43k, over the 6.0k that note 11 gives | 0.687 V rms (3.2) |

All match the architecture. The input stage's levels hold for **balanced** sources only; see M2
for unbalanced sources and overload.

### 2.2 Polarity of polarised parts

Every part below was checked in KiCad's netlist (pin 1 of `Device:C_Polarized` is +; zener pin 1
is K).

- **Electrolytics, all correct:**
  - C201 has + on +15V_RAW.
  - C206 has + on GND and - on -15V_RAW.
  - The input couplers have + on the op-amp side, which sits at VCOMAD (2.5 V), and - on the 1M
    bleed (0 V).
  - The output and headphone couplers have + on the DAC pin (2.5 V) and - on a 0 V node.
  - The converter caps have + to the pin.
  - On D, C2, C30 and C31 have + on 12V_P, C33 has + on +15V_FILT, and C35 has + on GND.
- **Diodes, all correct:**
  - D1 and D2 have their cathode at 12V_RP and their anode at the gate, clamping |Vgs| to 10 V.
  - D3 (SMBJ15A) has K on 12V_P.
  - D901, D902, D904 and D905 have A at the coil drain and K at the clamp node; D903 and D906
    have K at the clamp node and A at 5V_DIG (clamp 5 + 0.7 + 10 = 15.7 V).
  - Every TVS is bidirectional.
  - The LEDs have their anode to PANEL_3V3 through a resistor and K to the MCU line.
- **FETs, correct:**
  - Q1 (DMP3099L) has its drain on the input and its source on 12V_RP, so the body diode
    conducts only with correct polarity and the FET then enhances. Reversed, Vgs is about 0 and
    the FET is off.
  - Q2 has its source on 12V_RP and its drain on 12V_P, back to back with Q1, so when off its
    body diode blocks forward current.
  - The BSS138s are low-side, with source on GND.
  - Pins: SOT-23 G 1, S 2, D 3 for both FET types; MMBT3906 B 1, E 2, C 3.

### 2.3 Voltage ratings of capacitors

All pass. The tightest cases:

- 10 uF 25 V X7R 1206 on the 15 V rails: 60 % of rating. It derates to roughly 4 uF, which is
  still over the LDOs' 2.2 uF minimum.
- C2 1000 uF 25 V on 12V_P: 12 V nominal, 15.7 V at the cut-off, and the SMBJ15A clamp of about
  24 V under a surge. Very little margin under a surge, but acceptable.
- C1 100 nF 25 V sees only Vgs, at most 10 V.
- 22 uF 10 V X5R on 5V5_LC at 5.5 V: 55 %.

### 2.4 TPS563208 pins against the stock symbol

**Pass.** `Regulator_Switching:TPS563208` numbers its pins 1 GND, 2 SW, 3 VIN, 4 VFB, 5 EN,
6 VBST, which is SLVSD90B Table 4-1 for the DDC package. The footprint is TSOT-23-6 (DDC).

### 2.5 PCM3168A I2C address straps and mode

**Pass.**

- MODE (48) goes to GND through R401 0 ohm: "tied to DGND: I2C" (pin table, Table 6).
- ADR0 (45) and ADR1 (44) go to GND through 10k each. The address is 1 0 0 0 1 ADR1 ADR0 =
  **0x44** (9.3.14, Figure 43).
- MODE is sampled at RST's rising edge with SCKI present (9.4.1), and SCKI is present by default
  (1.3).
- The reset defaults are slave mode for both converters (MSDA = 000, 9.5) and differential ADC
  inputs, so the converter cannot fight the MCU on BCK or LRCK before it is configured.
- Every one of the 65 converter pins was checked against the pin diagram and pin table.

### 2.6 Headphone returns

**Pass.**

- **On A:** HP_L_RET and HP_R_RET join GND only through NT801 and NT802, which are to sit at
  U801's GND pin (3) with Rg's ground.
- **On PR:** HP_L_RET is the sleeve, and HP_R_RET joins it only through NT1. D8 and D9 are
  referenced to the sleeve. None of the four headphone nets touches PR's GND or POT_GND.
- **The cable:** J_HP pins 5 and 6 are open, so there is no second ground path from A to the
  panel. The two returns are in parallel end to end, as the architecture intends (4.3); the loop
  they form is the area between adjacent ribbon conductors.
- **The amplifier:** OPA1622 pins checked against SBOS727B: +INA 1, V+ 2, GND 3, V- 4, +INB 5,
  -INB 6, OUTB 7, EN 8, OUTA 9, -INA 10. The thermal pad (footprint pad 11) is on V-.

### 2.7 Chassis and ground bond

**Pass, with one dependence (m5).** There is one GND to CHASSIS bond: R90 0 ohm at H1 on D,
beside J5 and J1. Nothing else ties GND to CHASSIS:

- On D, the USB shell RC is DNP.
- A has no GND to CHASSIS link.
- PL and PR have no plated holes, and their MP pads are netless.

A's chassis strip reaches the case only through MH1, and D's H1 reaches the same case, so the
two strips join through the metal case alone.

### 2.8 Things that pass ERC but could fail the board

- The relay footprint's contact mapping and the coil polarity (section 4, item 2).
- The morpho sockets must be placed on D's underside, or the pin mapping mirrors (m10).
- Custom or stock symbols whose pin-out has no textual source here: PS1, PLR135, PLT133, TLV9001
  DCK, and the TL431's maker (section 4).
- PWR_FLAGs: every one on A, D, PL and PR was looked at, and each sits on a net that really is
  driven through a connector, link, ferrite or resistor. None hides a missing source.
- `GND` on D carries no flag, because PS1's 0V pin is a power output. If PS1 were ever removed,
  ERC would need the flag back (as D's notes say).

## 3. Findings, ranked

Severity: **blocker**, the board would not work or would be damaged; **major**, it works badly
or out of spec; **minor**, margin, cost or documentation. No blocker was found among the items
that could be checked. Section 4 lists the unchecked items that would be blockers if wrong.

### M1, major: the over-voltage switch's soft-start does not limit inrush (D: Q2, C1, R2, C2)

- **Read:** C1 100 nF sits from Q2's gate to its **source** (12V_RP), with R2 100k to GND.
- **Computed:** with the capacitor from gate to source, Vgs moves exponentially with a 10 ms time
  constant. Nothing ties the drain voltage's slope to the gate: there is no Miller feedback. Q2
  goes from off to fully on while |Vgs| crosses about 1.5 to 3 V, between 1.3 and 2.9 ms. After
  that the current into about 1.17 mF on 12V_P (C2 1000 uF, C30 100 uF, C31 47 uF, the bucks'
  ceramics) is set by the adapter, the cable, the PTC and the two FETs' Rds(on). The notes' 2.7 A
  assumes a 5 ms linear ramp that this circuit does not impose.
- **Computed:** whatever the ramp, charging 1.17 mF to 12 V dissipates 1/2 C V^2 = **84 mJ** in
  the series path at every plug-in, plus the bucks' load during the ramp. Q1 and Q2 are SOT-23
  parts.
- **Inferred:** a fast edge gives a peak of tens of amps through Q1, Q2 and the PTC. A slow
  linear ramp gives several watts for milliseconds in a SOT-23. Either is likely outside the
  DMP3099L's safe operating area [Verify against its SOA curve and by simulation, D's Verify
  item 1].
- **Fix:**
  - Move C1 to gate-drain (Q2_G to 12V_P), with a 1 to 10 kohm resistor in series with the gate
    node, so the Miller plateau sets dV/dt = (V across R2) / (R2 C1). With 100k and 100 nF that
    is about 1 V/ms and 1.2 A of charging current.
  - Then check the resulting about 7 W for about 12 ms against the SOA. If it fails, use a Q2 in
    a power package (for example a PowerDI3333 or DPAK P-FET), or the eFuse with OVP and reverse
    protection that arch 9 names as runner-up.
  - Simulate before layout.

### M2, major: the ADC input pins can be driven outside their limits (A: U501, U502, R 47R, U401 VIN1/2)

- **Read:** each ADC pin is limited to 1 V rms. SBAS452A 10.2.2.1 says an input filter can
  "reduce a 2-VRMS signal to a 1-VRMS input, which is the limit of the ADC input". Absolute
  maximum is -0.3 V to VCC + 0.3 V, with 10 mA input current (8.1).
- **Read:** each leg is an independent inverting stage from the ±12 V rails, centred on VCOMAD,
  feeding its ADC pin through only 47 ohm.
- **Balanced source, computed:** at 0 dBFS each pin swings 1.0 V rms. Correct.
- **Unbalanced source, computed:** a TS plug grounds the cold leg, so the hot leg's pin alone
  carries the whole signal. Reaching 0 dBFS needs 2.0 V rms on one pin: 2.83 V peak about
  2.5 V, that is **-0.33 V to 5.33 V**. That is past the absolute maximum at full scale, and past
  the stated 1 V rms per-pin limit from -6 dBFS (+14 dBu unbalanced). `rev_a_input_budget.md`
  section 6 ("0 dBFS is reached at +20 dBu on the hot leg") does not account for this.
- **Overload, computed:** the op-amp can swing to about ±11.2 V. The pin current passes 10 mA
  once the pin is about 1.07 V past a rail (0.6 V diode plus 0.47 V across 47 ohm). That happens
  at a leg peak of 14.0 V: **+22 dBu unbalanced or +28 dBu balanced**. Both are below the 15 V
  stand-off of the input TVS, so the TVS does not prevent it. The current is then limited only
  by the OPA1678's short-circuit current (about 50 mA, arch 9).
- **Fix:**
  - **(a) Unbalanced levels:** make the stage differential-out whatever the source's balance.
    For example, TI's Figure 58 and 59 pattern: a balanced receiver (difference amplifier around
    VCOMAD), then a unity inverter around VCOMAD for the other pin. Each pin then carries half
    the difference. That needs a new noise and CMRR budget [Verify].
  - **(b) Overload protection:** raise the series resistor to about 220 ohm, scaling the
    differential capacitor to keep about 160 kHz (12.1.3 allows 47 to 470 ohm). Add low-leakage
    Schottky clamps (for example BAT54S) from each ADC pin to 5V_ANA and GND, so overload current
    goes into the diodes rather than the converter [Verify the THD cost of the clamps'
    capacitance].
  - Either way, `rev_a_input_budget.md` section 6 needs correcting.

### M3, major: the supervisor's rising threshold leaves about 0.1 V to a 12 V adapter (D: U4, R40 to R42)

- **Computed:** without the part's own hysteresis, RAILS_OK releases at 10.73 V and falls at
  10.47 V. With about 1 % internal hysteresis and tolerances, D's notes put the rising threshold
  at up to 11.15 V.
- **Computed:** a 12 V adapter at -5 % (11.4 V), less the PTC and two FETs at 0.69 A, gives
  about 11.25 V. Cable drop and a warm PTC take more. The device can then stay muted, or
  RAILS_OK can chatter as the load changes when the relays close.
- **Computed:** the threshold does not need to be that high. The analogue hold-up comes mostly
  from the module's output capacitors (4.3 ms). With RAILS_OK falling at 9.7 V, 12V_P still
  gives 1.2 ms down to 9 V, so the total is **5.4 ms** against the relay's 3 ms.
- **Fix:** R40 237k (E96) gives **9.76 V falling and 10.04 V rising** (computed, before internal
  hysteresis), about 1.2 V below a -5 % adapter. Re-measure at bring-up step 4.

### m1, minor: input CMRR at mains frequencies is set by the coupling capacitors (A: C 10u 35V, input legs)

- **Computed:** each leg's input impedance is Rin plus the 10 uF coupling capacitor's reactance.
  With ±20 % electrolytics, the leg-gain mismatch alone limits CMRR to **35.6 dB at 20 Hz,
  43.6 dB at 50 Hz and 49.6 dB at 100 Hz**, worst case.
- That is worse than the 48 dB the 0.1 % resistors were bought for (budget section 5).
- **Fix:** 47 uF gives 57 dB at 50 Hz (computed) for a few pence; 100 uF gives more.

### m2, minor: the module's capacitive load is at its limit with no tolerance margin (A: C201/C202, C206/C207; D: C32 to C35)

- **Read:** each raw rail carries 110 uF on D and 110 uF on A: exactly the 220 uF of the YLPTEC
  listing.
- **Inferred:** with electrolytic tolerance (+20 %) it can reach about 260 uF, so start-up is not
  guaranteed under that limit. Mornsun's own figure is 680 uF.
- **Fix:** confirm which maker's part is fitted and its limit. If it is YLPTEC, use 68 or 82 uF
  for A's C201/C206. Hold-up is then still about 6 ms (computed).

### m3, minor: the pot inputs float with J_PANEL unplugged (D: R101 to R107, C101 to C107)

- **Read:** POTn_ADC has 1k to the ribbon and 100 nF to POT_GND, with no DC path once the panel
  is gone.
- **Inferred:** the monitor and phones volume pots (POT4, POT5) would read whatever charge
  drifts onto them.
- **Fix:** 1 Mohm from each POTn_ADC to POT_GND. The loading error at mid travel is about
  0.25 %, a fixed, ratiometric curve error. Alternatively, firmware treats an implausible
  all-pots pattern as "panel absent" and mutes.

### m4, minor: A-to-D inputs float with J_LINK unplugged (D: PC9 MCLK_MCU, PE3 DOUT1, PE12 CODEC_OVF)

- **Read:** none of the three has a pull resistor on D.
- **Read:** J7 also carries live 5V_DIG, 5V5_PRE and ±15V_RAW on open pins next to GND pins once
  the jumpers are bridged.
- **Fix:** 100k pull-downs on D for the three inputs, or firmware pulls on PE3 and PE12, with an
  I2S_CKIN time-out. Label J7 as live.

### m5, minor: A's chassis strip reaches circuit ground only through the metal case (A: MH1; D: H1, R90)

- **Read:** A's CHASSIS (jack sleeves, the input RF capacitors, every TVS) connects only to MH1.
  No cable carries CHASSIS between A and D.
- **Inferred:** on the bench without the case, A's ESD and RF parts and the jack sleeves float.
  A TS-plugged input then has no ground reference except two 1M bleeds. A TS plug in an output
  returns the shorted cold leg's current (up to about 43 mA peak) through the case and the bond
  in normal use. That is inherent and harmless, but worth knowing when hunting hum.
- **Fix:** document a bench strap from MH1 to D's H1 for lid-off work. Optionally add a CHASSIS
  wire or tab between the two boards' bond holes. That is a chassis-only path, so it adds no
  GND loop.

### m6, minor: RAILS_OK watches 12V_P only (D: U4; A: U901, U902)

- **Read:** a failed module, open JP3/JP4 or open 0 ohm links on A leave RAILS_OK high, so the
  firmware can unmute with dead analogue rails. No damage results.
- **Computed:** while ±12V_ANA is absent and 5V_ANA is up, the four OPA1678 + inputs' clamp
  diodes pull VCOMAD from 2.5 V to about 0.6 V. That sinks about 190 uA against VCOMAD's 1 uA
  rating (8.5).
- **Fix:** none needed in hardware if the firmware releases RST only after the ±12 V rails are up
  (they are, 189 ms after 12V_P, in the normal sequence). State that in the bring-up and firmware
  notes. Rename the signal, or add a ±12 V window comparator in rev B if wanted.

### m7, minor: board D's supervisor, I2C pull-ups and pot buffer depend on the Nucleo's 3.3 V (D: U4, R43, R53, R54, U8)

- **Read:** U4's VDD, RAILS_OK's pull-up and the I2C pull-ups all come from NUCLEO_3V3, and U8's
  input is VREFP. This has three consequences:
  - Architecture bring-up steps 1 to 4 ("main board without the Nucleo") cannot measure the
    RAILS_OK delay, its threshold or the power-fail timing.
  - Without the Nucleo, U8's input floats while its output, supplied from 5V_DIG, can sit
    anywhere up to 5 V on POT_REF.
  - With JP2 moved back to STLK for bench work and 12 V off, VREFP (3.3 V) back-powers the
    unpowered 5V_DIG net through U8's input clamp [Inferred, Verify the TLV9001 input
    structure].
- **Fix:** move the RAILS_OK and power-fail measurements to after step 5, and add a 1 Mohm
  pull-down at U8's + input. Alternatively, power U4 and R43 from a small LDO on 5V_DIG. Note in
  the bring-up text: never run the Nucleo from ST-LINK with D fitted and 12 V off.

### m8, minor: headphone enable timing (A: OPA1622 input couplers)

- **Computed:** at power-up VCOMDA rises with 7.5k x 10 uF = 75 ms. The two inputs' coupling
  networks have different time constants: 10 uF into 12.43k on the + side, about 10k on the -
  side, with ±20 % on each capacitor. That converts the common-mode ramp into a differential
  transient of a few tens of mV at the output, about 0.25 s after power-up, decaying over about
  1 s.
- **Fix:** in firmware, raise HP_EN no sooner than about 1 s after the converter leaves reset,
  or after power-save exits [Verify by measurement at bring-up step 9].

### m9, minor: MCLK_MCU termination over the ribbon (A: U302, R306; D: PC9)

- **Inferred:** the source impedance is 33 ohm plus the LVC2G34's roughly 20 ohm, against a
  signal-ground ribbon pair of roughly 100 ohm. The edge is therefore under-terminated over about
  60 mm of cable plus two board traces and the Nucleo's own trace to PC9, which is shared with
  CN8.
- Ringing on I2S_CKIN can double-clock the SAI kernel clock [Verify by scope, bring-up step 6].
- **Fix:** a 0603 footprint for an optional series resistor or RC at the D end, or raise R306 to
  about 68 ohm after measurement.

### m10, minor (layout-critical): the morpho sockets must be on D's underside (D: J2, J3)

- **Read:** J2 and J3 are `PinSocket_2x35` footprints that mate with headers on the Nucleo below
  D.
- **Inferred:** on the top side, pin n would land over the wrong row. Placed on B.Cu, KiCad
  mirrors the pads correctly.
- **Fix:** a note on the sheet and a stage 4 check. Also check against the Nucleo's drawing that
  CN11 and CN12 are where D expects them, not swapped (V14).

### m11, minor: the 12V_P TVS clamps above the bucks' absolute maximum (D: D3 SMBJ15A)

- **Read:** the clamp is about 24 V at the rated pulse current. TPS563208 VIN is 19 V absolute
  maximum (SLVSD90B 5.1).
- **Inferred:** the TVS protects against nothing the bucks would not already survive. The
  1000 uF and the PTC do the real work against cable transients. D's notes say as much.
- **Fix:** none required; document only. A lower TVS is not an option: an SMBJ12A (13.3 V
  minimum breakdown) would conduct below the 15.7 V cut-off, at the top of a tolerant adapter's
  range. Keep the SMBJ15A.

### m12, minor: total capacitance on 5V_DIG against the buck's stated range (D: U2; A: C101; the Nucleo)

- **Read:** SLVSD90B Table 7-2 gives 20 to 68 uF of output capacitance.
- **Computed:** 5V_DIG carries 2 x 22 uF at the buck, C50 10 uF at the morpho, C101 10 uF on A
  (behind the ribbon) and the Nucleo's own 5 V capacitors [Verify their value]. That is 64 uF
  plus the Nucleo's.
- **Inferred:** trace and cable inductance decouple some of it, but the D-CAP2 loop's stability
  outside the table is not documented.
- **Fix:** check the load step at bring-up, or drop C50 to 1 uF.

### m13, minor: documentation corrections

- A's NOTES.md section 2: TPS7A30 soft-start is 0.9 ms/nF (SBVS125D Eq. 1), so **9 ms**, not
  14 ms. That closes its [Verify] item 3.
- D's NOTES.md and A's NOTES.md give the hold-up as about 5 ms. The figure computed here, with
  derated ceramics and 12V_P's full capacitance, is 6.7 ms (or 5.4 ms with M3's threshold).
- Bring-up step 4 should pull the adapter from the **mains** as well as at the barrel. Q1 and Q2
  conduct in both directions when on, so an adapter left plugged into the jack can load C2
  backwards through its own output circuit [Inferred, Verify].
- `rev_a_input_budget.md` section 6, as in M2.

## 4. To verify before layout

Unverified pin-outs (each would be a blocker if wrong):

1. **PS1 WRA1215S-3WR2 pin numbers.** `rev_a` symbol: 1 GND, 2 Vin, 3 Ctrl, 6 +Vo, 7 0V, 8 -Vo,
   taken from a drawing. Check against the datasheet's "Dimensions and Recommended Layout". Also
   confirm which maker's part is bought (YLPTEC or Mornsun) and its capacitive-load limit (m2),
   and the position of Fig. 2's Cd (47 nF / 100 V).
2. **Omron G6K-2F-Y in the stock footprint.** Check that pads 12, 11 and 14 (positions 2, 3, 4
   along each side) really are NC, COM and NO on Omron's terminal drawing. If NC and NO were
   swapped, the jacks would see the stage when off and ground when on, and every power-up thump
   would reach the monitors. Also check the coil polarity: A1 at the pin 1 corner goes to
   5V_DIG, and the G6K is polarised.
3. **TL431 in SOT-23.** TI's DBZ is 1 cathode, 2 REF, 3 anode (D's notes, SLVS543S), matching the
   symbol. Other makers' SOT-23 TL431s differ, so pin the BOM to the TI part or check the second
   source's drawing.
4. **TLV9001 DCK.** The symbol has 1 IN+, 2 V-, 3 IN-, 4 OUT, 5 V+, which differs from the DBV
   package. Check SBOS833 Table 6-1, and keep the DCK suffix in the BOM.
5. **PLR135 and PLT133** pin-outs and a current receiver part (DNP, batch 10, V25).
6. **Oscillators (V22):** pin 1 OE active high, output tri-stated when disabled, 3225 land, and
   jitter.

Land patterns:

7. PCM3168A: the PAP0064 land against the footprint's EP. SBAS452A gives a 7.25 x 7.00 mm pad;
   the footprint has 8 x 8 mm copper with 5 x 5 mm paste.
8. OPA1622 DRC against `Texas_S-PVSON-N10`, which is taken from the TPS61201's DRC.
9. The TPS7A49 and TPS7A30 DGN pad against HVSSOP 1.57 x 1.89 mm.

On the Nucleo (V29, V30):

10. Continuity of CN12-12 to PA12 and CN12-14 to PA11 (not PE6). The Nucleo's 5V_EXT current.
    PE15 and PC9 are FT.
11. The Nucleo's mounting holes and the standoffs, and whether the holes are plated to GND.

Mechanical and grounding:

12. The NMJ6HCD2 ferrule contact (V28). The DC jack's body is isolated from its negative contact
    (otherwise a second bond, though co-located with H1). RK09L terminal 3 is the clockwise end.

Parts not yet chosen, or ratings not read:

13. F1 PTC (1812, at least 1.1 A hold, at least 24 V); DC jack; power switch.
14. DMP3099L SOA and Vgs rating (M1).
15. Inductors: SRN6045TA-4R7M Isat and Irms; SRN4018 ratings; L201 2.2 uH DCR and saturation.
16. Ferrites: 600 ohm 0603 and BLM18PG221SN1.
17. TVS parts: PESD15VL1BA is a placeholder; PESD12VL1BA's capacitance and clamp.
18. Buttons: B3F-5000 against the 9 and 10 mm pitch.
19. Pots: detent part numbers.
20. Amber LEDs.
21. The OLED module's pin-out.
22. BSS138 Rds(on) at Vgs = 3.3 V.

Behaviour:

23. Unused DAC 7 and 8 outputs left open (SBAS452A silent).
24. The pot buffer's phase margin with C82 and up to 70 nF of wiper capacitance, by simulation.
25. The over-voltage cut-off and inrush, by simulation (M1).

## Resolution (2026-11-19)

- **M1** and **M3** fixed on board D as proposed (C1 gate to drain, 470 nF, Q2 FDS9435A in SO-8;
  R40 237 k). ERC 0 errors, 0 warnings; `check_links.py` passes. Details in
  `hw/rev-a/d/NOTES.md`, "Changes after the schematic review". The cut-off still needs a
  simulation before layout.
- **M2** is open: it changes the input stage's topology (the owner's EX5 subject), so it waits
  for the owner's decision.
- The minor findings and the verify-before-layout list wait for the owner's review.

## From the transcripts

Read for stage 3: #78 (mixed-signal hardware walkthrough) in full, again; #142 (codec driver)
was read in stages 1 and 2 and adds nothing to the schematic beyond the I2C address straps.

- **#78:** Phil's checklist habits, used as review items here: one 100 nF per VDD pin plus bulk
  (item 1); 33 ohm series resistors on clock lines at the transmitter (item 3); address-select
  pins strapped with 10 k (item 2.5 here: the PCM3168A's ADR pins); an RF low-pass and ESD at
  each audio input and a 100 ohm build-out at each output (checked on board A); a filtered
  supply and an RC on each pot's ADC input (board D); differential pairs named _P and _N
  (USB_D_P, USB_D_N). His input bias resistor "of a high value" is board A's 1 M bleed.
- **#78** also uses a 5 V single-supply analogue section; this design uses +/-12 V, so the
  converter's 5 V analogue inputs meet stages with a wider swing than in his board. That
  difference is exactly where finding M2 sits: his unity-gain followers on 5 V cannot exceed
  the converter's pins, ours can.
