# Rev A architecture (batch 5, stage 2)

**Still open after the source checks (2026-11-18):** DS12919 and RM0399 could not be fetched
(st.com timed out), so the alternate functions, the S/PDIF output on SAI block A and the OTG_FS
termination stay [Verify]; the Nucleo's heights (UM2408 Figure 5 is an image) and the Neutrik
drawings (the technical sheets carry none) wait for calipers and a sample. Everything else in
the stage 2 list is drafted.

Written 2026-11-18. Stage 2 of batch 5 (`docs/PLAN_BATCHES.md` section 7), after the owner's
stage 1 decisions (`part_selection.md` section 7). Everything here is a **proposal for the owner's
sign-off**; nothing is in the SPEC decision log as decided until he says so. Companion files:

- `docs/notes/pin_plan.md`: every signal onto the Nucleo-H755ZI-Q headers, checked against the
  board manual.
- `docs/notes/mechanical_interface.md`: outlines, holes, connector and control positions, stack
  height.
- `docs/notes/rev_a_input_budget.md`: the line input stage's levels, noise and dynamic range.
  **Do the exercise `docs/exercises/EX5_input_budget.md` first.** This note keeps the input
  stage's numbers out on purpose and refers to that file.

## 0. How far the figures can be trusted

- **Datasheets read in full text this session** (downloaded from ti.com and read with
  `pdftotext`): PCM3168A SBAS452A (Jan 2016), OPA1622 SBOS727B, OPA167x SBOS855E, TPS7A49
  SBVS121E, TPS7A30 SBVS125D, TPS56320x, TPS7A20 SBVS338H (Jul 2024); Mornsun WRA_S-3WR2 &
  WRB_S-3WR2 datasheet 2024.02.28-B; Neutrik technical information sheets for NMJ6HCD2 and
  NJ6FD-V (dated 18.11.2026; they carry no drawings). Board manual UM2408 Rev 6 (Feb 2025), from
  the owner's `Downloads` folder. Figures from them carry the section or table.
- **Not reachable this session:** DS12919 (STM32H755xI datasheet, Rev 2 Feb 2023) and RM0399
  (reference manual): st.com timed out on five attempts, and the only mirror found shows the table
  of contents.
- **Pin alternate functions** come from the STM32CubeMX 6.15 database shipped with STM32CubeIDE
  1.19.0 (`STM32H755ZITx.xml`, `GPIO-STM32H747_gpio_v1_0_Modes.xml`), which encodes the
  datasheet's alternate-function table, cross-checked against the AF macros of the pinned HAL
  1.11.5 (`stm32h7xx_hal_gpio_ex.h`): they agree for every peripheral used. Still a proxy for
  DS12919 [Verify].
- **Live prices and stock.** The LCSC and JLC part pages were reached read-only (for example
  C48888070, C2876559, C368502), but both sites render price and stock by script, and the fetch
  tool saw neither. Where a figure is given it is a search-index snapshot, marked "snapshot,
  seen 2026-11-18". V21 stays open: the owner reads them in a browser, or JLC's BOM tool does at
  stage 5.
- **Noise arithmetic.** Resistor noise sqrt(4kTR) at 25 C: 4.06 nV/rtHz per sqrt(kOhm). A-weighted
  bandwidth for white noise, 20 Hz to 20 kHz (the converter datasheets' measurement band):
  **12.47 kHz**, so sqrt(B) = 111.7 (computed by integrating the IEC A-weighting curve, normalised
  to 0 dB at 1 kHz; 13.46 kHz without the 20 kHz limit). Op-amp 1/f noise is ignored; A-weighting
  suppresses it. 0 dBu = 0.7746 V rms.

## 1. From the transcripts

Read in full for this stage: "Mini 6-Layer Mixed-Signal Hardware Design Walkthrough" (#78) and
"How To Write A Driver (Audio CODEC & I2C)" (#142), again. All 29 searched for regulators, LDOs,
grounding, ground planes, decoupling, op-amps, headphones, line level and anti-aliasing: the only
other relevant passage is in "Digital Audio Processing with STM32 #1" (a switching regulator for
the digital supply, an LDO for the analogue supply). #117 and #42 mention anti-aliasing filters
only as DSP topics.

**Taken:**

- Switcher for the digital supply, LDO for the analogue (#1, #78). Here: two bucks and an isolated
  module make raw rails; every analogue rail and the converter's 5 V come from an LDO.
- Codec reset held by a pull-down until the rails are stable; the clock present before
  configuration; power the codec down before changing its configuration; read back every
  register written (#142). Section 8 and bring-up step 7. The PCM3168A also wants its MCLK
  present for the mode pin to be sampled and for the internal reset to finish (SBAS452A 9.3.6,
  9.4.1).
- The input protection pattern (#78): ESD diode, an RF filter of a few hundred kHz to 1 MHz before
  any semiconductor, a coupling capacitor, a high-value resistor setting the input impedance.
  Output: about 100 ohm build-out against cable capacitance, ESD, a bleed resistor. Section 9.
- Low-impedance design to keep Johnson noise down (#78, its 1 k / 1 k reference divider). Here it
  is quantified per resistor in section 4.
- Series resistors of about 33 ohm at clock sources (#78); one 100 nF per supply pin plus bulk
  (#78), here with the 1 uF plus 10 uF that SBAS452A 12.1.1 asks for.
- Pot inputs: series resistor and capacitor at each ADC input (#78). Section 11.
- USB-C: 5.1 k on each CC pin separately (#78). Section 10.
- The codec as an I2C slave with its address set by strap pins (#142). The PCM3168A's control
  mode is itself a strap: MODE tied to DGND selects I2C (SBAS452A Table 6) [Verify, the table is
  garbled in the text extraction].

**Not taken, and why:**

- The RC filter (10 ohm, 47 uF) that makes an analogue 5 V from the digital 5 V (#78): the
  PCM3168A draws 162 mA typical, 210 mA maximum on its 5 V pins (SBAS452A 8.5), so 10 ohm would
  drop 1.6 to 2.1 V. It gets its own LDO instead (section 5). An RC or ferrite filter stays for
  the oscillators' supplies.
- Floating USB shield (#78): this device has a metal case; the shell goes to the chassis strip
  (section 7).
- 6 layers, impedance control, the USB switch and the mid-mount USB-C (#78): full-speed USB on a
  4-layer board needs none of them.
- Rail-to-rail CMOS op-amps biased at half supply (#78): split rails here.
- #142's codec drops into standalone mode unless a register is written soon after reset; the
  PCM3168A instead samples its MODE pin at reset, so the strap must be right in the schematic.

## 2. Block diagram

```
12 V DC -> switch -> PTC -> reverse-polarity FET -> over-voltage cut-off -> TVS -> 12V_P (bulk)
   12V_P -> TPS563208 #1 (5.0 V) -> 5V_DIG -> Nucleo 5V_EXT (CN11-6); relay coils;
                                            AMS1117-3.3 -> 3V3_DIG (codec VDD, clocks, optics)
   12V_P -> TPS563208 #2 (5.5 V) -> LC -> TPS7A2050 -> 5V_ANA (codec VCCAD1/2, VCCDA1/2)
   12V_P -> WRA1215S-3WR2 (isolated, 9-18 V in, +/-15 V 100 mA) -> LC -> TPS7A4901 / TPS7A3001
                                                                    -> +/-12V_ANA (all op-amps)
   12V_P -> supervisor -> RAILS_OK (open drain: forces mute in hardware, and to an MCU input)

24.576 MHz osc (OE) --+
22.5792 MHz osc (OE) -+-> 74LVC1G157 -> 74LVC2G34 -> 33 R -> PCM3168A SCKI
                                                  -> 33 R -> MCU PC9 (I2S_CKIN, SAI kernel clock)

MCU SAI1 (master, TDM 8 x 32 bit, BCK 256 fs) <-> PCM3168A: BCK, LRCK (ADC and DAC tied), DIN1, DOUT1
MCU I2C1 <-> PCM3168A control (address 0x44); GPIO -> RST (pull-down), MCU <- OVF

LINE IN 1, 2 (TRS) -> ESD, RF filter -> coupling C -> OPA1678 inverting attenuator x 2 legs
                   -> RC -> ADC 1, 2 differential (centred on VCOMAD)    [rev_a_input_budget.md]
DAC 1, 2 -> per leg: AC coupling, 2nd-order MFB low-pass, gain 2.16 (OPA1678)
         -> 100 R -> relay (DPDT, NC grounds the jack) -> ESD -> MONITOR OUT L, R (TRS, balanced)
DAC 5, 6 -> the same, parts optional -> LINE OUT 3, 4 (TRS, balanced)
DAC 3, 4 -> AC coupling -> OPA1622 difference amplifier, gain 0.243, EN = mute -> 1 R
         -> ribbon (dedicated return pair) -> PHONES jack on the panel board
DAC 7, 8, ADC 3 to 6: unused (terminated per SBAS452A 12.1.3)

Toslink RX -> PD7 (SPDIFRX1_IN0)        PD11 (SAI2_SD_A, S/PDIF mode) -> Toslink TX   [footprints]
USB-C (rear) -> USBLC6-2SC6 -> morpho CN12-12/14 (PA12/PA11, OTG_FS); VBUS -> divider -> PE15
Ribbon 2 x 20 -> panel board: 7 pots, 5 buttons, 7 LEDs, phones, OLED and encoder header
```

Outputs 3 and 4 as balanced line outputs use DAC 5 and 6, not DAC 3 and 4: the converter has
eight DACs, so the line outputs get levels independent of the headphone volume at no hardware
cost, and the firmware can send them the headphone mix or a crossover band. [Owner confirms.]

## 3. Levels

### 3.1 The proposal

| Point | 0 dBFS | Nominal (+4 dBu signal) | Headroom over nominal |
|---|---|---|---|
| Line inputs 1, 2 | **+20 dBu** (7.75 V rms, balanced) | -16 dBFS | 16 dB |
| Monitor outputs L, R and line outputs 3, 4 | **+18 dBu** (6.10 V rms, balanced; +17.9 dBu with E24 parts) | -14 dBFS | 14 dB |
| Headphones | **0.687 V rms into 38 ohm, 12.4 mW, 109.9 dB SPL** on the ATH-M50x | n/a | n/a |

Why these:

- **Input +20 dBu** keeps the SPEC proposal: 16 dB over +4 dBu covers typical line sources, whose
  peaks rarely pass +20 dBu. What it costs in noise and headroom against +18 or +24 dBu is worked
  in `rev_a_input_budget.md`. In one line, without numbers: the input's dynamic range is set by
  the ADC whatever the choice, so a higher 0 dBFS buys headroom with the same number of dB of
  signal-to-noise at nominal level.
- **Output +18 dBu** keeps the SPEC proposal and is mainstream for interfaces (EBU R68 puts 0 dBu
  at -18 dBFS). The dynamic range of the output is the DAC's whatever the value (section 4); a
  higher value only raises the absolute noise floor at the monitors and risks overdriving monitor
  inputs that clip at +20 dBu or below [owner checks his monitors' maximum input level]. Checked
  against the rails: each leg peaks at 4.31 V at 0 dBFS; the OPA1678 swings to within 0.8 V of the
  rails into 2 kohm (SBOS855E features), so +/-11.2 V on +/-12 V rails: the analogue stage clips
  20 log(11.2 / 4.31) = **8.3 dB above 0 dBFS**. The DAC always clips first.
- The 2 dB gap between input and output means a 0 dBFS input reaches the monitors at 0 dB digital
  gain 2 dB lower than it came in. That is harmless for a monitoring path whose volume is a DSP
  gain anyway; equal values would need either 2 dB less input headroom or 2 dB more output level.
- **Headphones** as the owner set: about 110 dB SPL at full scale. Arithmetic, assuming the
  ATH-M50x's 99 dB is per mW [Verify]: 110 - 99 = 11 dB over 1 mW = 12.6 mW;
  V = sqrt(0.0126 x 38) = 0.69 V rms, 0.98 V peak, 25.8 mA peak. A 300 ohm headphone gets
  1.6 mW at full scale from the same stage; whether that is loud enough depends on its
  sensitivity [owner says if other headphones matter].

### 3.2 Level diagram, output chains (at 0 dBFS, 1 kHz)

| Stage | Gain | Level out | Source |
|---|---|---|---|
| DAC (VCCDA = 5.0 V) | n/a | 1.6 x 5.0 = 8 V pp differential = 2.828 V rms diff (+11.2 dBu), centred on 2.5 V | SBAS452A 8.5, 9.3.2 |
| Monitor/line stage, each leg: AC coupling, MFB low-pass (R1 5.1 k, R2 11 k, R3 360 ohm) | -R2/R1 = -2.157 (+6.7 dB) | 6.100 V rms diff = **+17.9 dBu**, ground-centred | computed |
| Build-out 100 ohm per leg, relay, jack | about 0 dB into 10 kohm | +17.9 dBu | |
| Headphone stage, OPA1622 difference amplifier (Rin 10 k, Rf 2.43 k) | 0.243 (-12.3 dB) | 0.687 V rms single-ended | computed |
| Build-out 1 ohm, ribbon (about 33 mohm per conductor [Verify]), 38 ohm load | -0.23 dB | 0.669 V rms at the headphone | computed |

The stage values are first picks for the noise budget; stage 3 sets the capacitors for a
second-order low-pass near 55 kHz (TI's examples: 53 to 54 kHz, SBAS452A Figures 61 and 62).
The DAC pins must see at least 5 kohm when AC-coupled (SBAS452A 8.5, note 11): R1 = 5.1 k at the
inverting input's virtual ground meets it; the headphone stage's 10 k exceeds the
(1 + 2G)/(1 + G) x 5 k = 6.0 kohm that note 11 gives for G = 0.243.

The input chain's level diagram and gains are in `rev_a_input_budget.md`.

## 4. Noise budget, output and headphone chains

Method: each source's noise density referred to the stage output, summed in power, the two legs
of a differential path as independent, then times sqrt(12.47 kHz) = 111.7 for A-weighted rms.
The DAC's own floor is its dynamic range below full scale: 2.828 V / 10^(112/20) = **7.10 uV(A)**
differential (SBAS452A 8.5, 112 dB typical, EIAJ, A-weighted, 48 kHz).

### 4.1 Monitor outputs (and line outputs 3, 4)

Per leg, MFB with G = 2.157, noise gain 1 + R2/R1 = 3.157:

| Source | Density at source | Gain to output | At output (nV/rtHz) |
|---|---|---|---|
| R1 5.1 k | 9.16 | 2.157 | 19.76 |
| R2 11 k | 13.47 | 1 | 13.47 |
| R3 360 ohm | 2.44 | 3.157 | 7.69 |
| OPA1678 e_n | 4.5 (SBOS855E, 1 kHz) | 3.157 | 14.21 |
| OPA1678 i_n | 3 fA/rtHz x 11 k | 1 | 0.03 |
| **Leg total** | | | sqrt(390.5 + 181.4 + 59.2 + 201.9) = **28.86** |

Differential: 28.86 x sqrt(2) = 40.82 nV/rtHz; x 111.7 = **4.56 uV(A)**.
DAC floor through the stage: 7.10 x 2.157 = **15.32 uV(A)**.
Total: sqrt(15.32^2 + 4.56^2) = **15.98 uV(A) = -93.7 dBu(A)**.
Dynamic range: 20 log(6.100 / 15.98e-6) = **111.6 dB(A)**, against 112 dB for the DAC alone: the
stage costs 0.4 dB. Target 105 dB (SPEC 3.3): met with 6.6 dB to spare, on paper.

What moves it: R3 is in series with the op-amp's input at a noise gain of 3.2, so it must stay
small (360 ohm adds 0.07 dB; 1 k would add about 0.4 dB more). Raising the output to +20 dBu
changes the DR by under 0.1 dB and the floor by +2 dB. The 100 ohm build-out resistors add
1.28 nV/rtHz each, nothing visible.

### 4.2 Headphones

OPA1622 difference amplifier, G = Rf/Rin = 2.43/10 = 0.243, inputs AC-coupled:

| Source | Density at source | Gain to output | At output (nV/rtHz) |
|---|---|---|---|
| Rin, inverting side, 10 k | 12.83 | 0.243 | 3.12 |
| Rf 2.43 k | 6.33 | 1 | 6.33 |
| Rin parallel Rg at the + input, 1.955 k | 5.68 | 1.243 | 7.06 |
| OPA1622 e_n | 2.8 (SBOS727B, 1 kHz) | 1.243 | 3.48 |
| OPA1622 i_n, each input | 0.8 pA/rtHz x about 2 k | about 1.2 | 1.94 each |
| **Total** | | | sqrt(119.2) = **10.92** |

Stage: 10.92 x 111.7 = **1.22 uV(A)**. DAC floor through the stage: 7.10 x 0.243 = **1.73 uV(A)**.
Total: **2.11 uV(A)**. Dynamic range: 20 log(0.687 / 2.11e-6) = **110.3 dB(A)**; the stage costs
1.7 dB against the DAC. In sound: (2.11 uV)^2 / 38 ohm = 1.2e-10 mW = -99.3 dBm, so about
**0 dB SPL** of hiss at 99 dB/mW: inaudible.

What moves it: the resistors dominate, not the OPA1622. Rin = 6.8 k with Rf = 1.65 k (still above
the DAC's 6.0 k minimum) would win about 0.6 dB; not worth a value off the E24 list now. Stage 3
may revisit. DC at the jack: inputs AC-coupled, so the DC gain is 1 from the op-amp's offset
(0.5 mV max, SBOS727B) plus I_OS x Rf = 50 nA x 2.43 k = 0.12 mV: under 1 mV, 16 uA in 38 ohm.

### 4.3 Crosstalk, honestly

- Monitor and line outputs: each leg is its own stage, and the PCM3168A's DAC channel separation
  is 108 dB typical (SBAS452A 8.5); layout decides the rest. -90 dB is plausible [measure in
  batch 7].
- **Headphones cannot reach -90 dB.** Left and right share the TRS sleeve: any impedance common
  to both returns turns one channel's current into the other's signal at R_common / R_load. The
  jack's own contact is up to 15 to 30 mohm (Neutrik NMJ6HCD2 page, 2026-11-18), so even with
  perfect wiring 20 log(0.015 / 38) = -68 dB. With the two ribbon returns in parallel added (16 mohm
  [Verify]) about -64 dB. This is a property of any headphone output on a TRS jack. SPEC 3.3's
  crosstalk row should say "line outputs" [owner confirms].

## 5. Power tree and current budget

### 5.1 Rails

| Rail | Made by | Feeds | Why this part |
|---|---|---|---|
| 12V_P | 12 V adapter, PTC, reverse-polarity P-FET, over-voltage cut-off, TVS, 1000 uF bulk | everything | section 9 |
| 5V_DIG | TPS563208 (5.0 V) | Nucleo 5V_EXT, relay coils, 3V3_DIG | see note below on 201 vs 208 |
| 3V3_DIG | AMS1117-3.3 from 5V_DIG | PCM3168A VDD1/2, oscillators (each through a ferrite and 10 uF), mux, buffer, optical modules, supervisor | JLC Basic part [Verify class]; a digital rail |
| 5V5_PRE | TPS563208 (5.5 V) | 5V_ANA LDO only | keeps the LDO's drop to 0.5 V |
| 5V_ANA | TPS7A2050 (300 mA, 7 uV rms, 6 V max input) after an LC filter | PCM3168A VCCAD1/2, VCCDA1/2 | sized for 210 mA max (below) |
| +/-15 V raw | WRA1215S-3WR2, isolated, 9 to 18 V in, +/-15 V 100 mA, 300 kHz | analogue LDOs | sized for 90 mA worst case (below) |
| +/-12V_ANA | TPS7A4901 (150 mA) / TPS7A3001 (200 mA) after an LC filter | every OPA1678 and the OPA1622 | as accepted in stage 1 |
| Nucleo 3V3 | the Nucleo's own U11 (1300 mA max, UM2408 7.4.7) | panel board logic: LED anodes, pull-ups, OLED, encoders | same rail as the MCU's I/O: nothing back-powers the MCU |
| VREFP | the Nucleo's VREF+ (= VDDA = VDD through R40, UM2408 Table 16) | pot tops | ratiometric with the ADC |

**TPS563208 instead of the TPS563201 accepted in stage 1 [owner decides].** The 201 runs in
pulse-skip mode at light load, its frequency falling with load (TPS56320x features and Figure
5-8); the 208 runs continuous-current mode at a fixed 580 kHz. Skip mode starts below about half
the inductor's ripple current: with 4.7 uH, 12 V to 5.5 V, ripple = (12 - 5.5) x (5.5/12) /
(4.7 uH x 580 kHz) = 1.09 A, so the 5.5 V rail at 0.2 A would skip, at a frequency that can fall
into the audio band. Same package and pin-out, LCSC C468250 (snapshot: 75 160 in stock from
$0.076; another snapshot 1820 at $0.145; seen 2026-11-18). The cost is efficiency at light load,
irrelevant here.

**Why the converter's 5 V is not made from +15 V:** 210 mA from the +15 V module rail would need
a 6 W module and burn (15 - 5) x 0.21 = 2.1 W in the LDO. From 12 V directly it would burn 1.5 W.
A second buck at 5.5 V and a small LDO burn 0.1 W.

### 5.2 PCM3168A supply current (SPEC V23)

SBAS452A 8.5, power-supply requirements, at 5 V / 3.3 V, 48 kHz, 512 fs:

| Supply | Typical | Maximum |
|---|---|---|
| ICC, VCCAD1/2 + VCCDA1/2 (5 V) | 162 mA | 210 mA |
| IDD, VDD1/2 (3.3 V) | 106 mA | 130 mA |
| Power dissipation | 1160 mW | 1480 mW |

The stage 1 rule ("TPS7A4901 if under about 120 mA") fails: 210 mA is over its 150 mA. Chosen:
**TPS7A2050** (300 mA, so 70 % at the maximum). From SBVS338H: input 1.6 to 6.0 V, 6.5 V absolute
maximum (5.1); dropout 140 mV (DQN) or 145 mV (DBV) maximum at 300 mA for outputs of 2.5 to
5.5 V; current limit 360 mA minimum; PSRR at a 300 mA load 92 dB at 1 kHz, 75 dB at 10 kHz, 60 dB
at 100 kHz, 40 dB at 1 MHz; noise 7 uV rms, 10 Hz to 100 kHz (5.5). From 5.5 V:
(5.5 - 5.0) x 0.21 = 0.11 W: +18 C in the X2SON (166.1 C/W, 5.4), +6 C in the SOT-23-5 (54.4 C/W).
The buck's 5.5 V +/- 2 % stays inside the 6.0 V operating maximum. The SOT-23-5
`TPS7A2050PDBVR` is in TI's orderable list (SBVS338H, packaging addendum) but was not found at
LCSC; the 1 x 1 mm `TPS7A2050PDQNR` is (C2866499, snapshot 650 in stock) [Verify JLC can place
it, or pick the runner-up]. Runner-up: TPS7A4701 (1 A, 36 V) from 6.5 V.

Why its noise matters little: the PCM3168A's ADC reference is VCCAD1 itself (VREFAD1 = VCCAD1,
SBAS452A 8.5) and the DAC's full scale is 1.6 x VCCDA1, so supply noise modulates the gain, a
multiplicative error: 7 uV on 5 V is -117 dB relative to the signal. The common-mode pins are
filtered by their 10 uF capacitors against 7.5 to 10 kohm. The LC filter (2.2 uH, 22 uF: corner
23 kHz, about -56 dB at 580 kHz) and the LDO's PSRR keep the buck's ripple under 1 uV.

### 5.3 Analogue rails: is 2 W enough? No: the 3 W module

Per rail, all outputs at 0 dBFS sine (the honest sizing case):

| Load | Typical | Worst case | Source or arithmetic |
|---|---|---|---|
| 6 x OPA1678 (12 channels: inputs 4, monitor 4, line 3/4 4) | 24.0 mA | 30.0 mA | 2.0 / 2.5 mA per channel, SBOS855E |
| OPA1622, 2 channels | 5.2 mA | 6.6 mA | 2.6 / 3.3 mA per channel, SBOS727B |
| Headphone load, both channels, 25.6 mA peak | 16.3 mA | 16.3 mA | average per rail = 2 x Ip / pi |
| 8 output legs into 10 k balanced (5 k per leg, conservative) | 2.2 mA | | 4.31 V / 5 k / pi x 8 |
| 8 output legs into 600 ohm balanced (300 per leg) | | 36.6 mA | 4.31 V / 300 / pi x 8 |
| Feedback networks (R2 11 k) | 1.0 mA | 1.0 mA | |
| **Total per rail** | **48.7 mA** | **90.5 mA** | |
| Idle, no signal | 29.2 mA | 36.6 mA | |

- The 2 W module (66 mA per rail) covers the typical case at 74 % and fails the worst case at
  137 %. **The 3 W module (100 mA) covers the worst case at 91 %.** A 6 W module is not needed.
- **WRA1215S-3WR2.** Mornsun's datasheet (2024.02.28-B): 9 to 18 V input; +/-15 V at 100 mA
  maximum and **5 mA minimum** per output; efficiency 81 % minimum, 83 % typical; voltage accuracy
  +/-1 % typical, +/-3 % maximum; load regulation +/-0.6 % typical; maximum capacitive load
  680 uF per output; switching **250 kHz in PFM mode** at full load and nominal input (so the
  frequency moves with load); the two outputs' loads should match within +/-5 %; isolation
  1500 V dc, 120 pF; 22 x 9.5 x 12 mm SIP; recommended circuit (its Fig. 2) 100 uF / 25 V at the
  input, 2.2 to 10 uH and capacitors at the outputs. The LCSC part is YLPTEC's (C5369659; its
  listing says 300 kHz, 100 mV pp, **220 uF** maximum load; stock 210 in a search snapshot); the
  YLPTEC datasheet itself only opened as a viewer page, not as text. The design keeps to the
  stricter of the two: at most 220 uF per output, and a filter that works from 250 kHz down. The
  wide input removes the stage 1 worry that the 2 W part (10.8 to 13.2 V) needs a 12 V adapter
  within 10 %, and it rides through to 9 V when 12 V is pulled (section 8). Our loads are
  symmetric to within the 5 % (the op-amps' and headphones' currents are drawn equally from both
  rails on average) [measure at bring-up, with the module's frequency at the idle load of about
  30 mA].
- Filtering: module, then 22 uH and 100 uF per rail (corner 3.4 kHz, about -75 dB at 250 kHz),
  so about 100 mV pp of ripple is about 18 uV at the LDO, which rejects at least 52 to 55 dB more
  (TPS7A49/30 features). Total capacitance per rail stays within 220 uF. If PFM pulls the
  frequency below about 30 kHz at idle, the filter still gives over 35 dB there [Verify on the
  bench].
- LDO dissipation at 90.5 mA: (15 - 12) x 0.0905 = 0.27 W each (HVSSOP PowerPAD).
- Module input: worst 30 V x 90.5 mA / 0.8 = 3.4 W; typical 1.8 W; idle 1.1 W.

### 5.4 Digital 5 V and the 12 V input

| Load on 5V_DIG | Typical | Maximum | Note |
|---|---|---|---|
| Nucleo own consumption (MCU at 400 MHz, ST-LINK, Ethernet PHY, LEDs) | 300 mA | 350 mA | **estimate**; measure (V29, bring-up step 0) |
| Panel 3.3 V through the Nucleo's U11: 7 LEDs at 2.5 mA, OLED (batch 11) about 25 mA [Verify], pots 2.3 mA | 46 mA | 46 mA | counts against 5V_EXT's 500 mA |
| 3V3_DIG: PCM3168A VDD 106 / 130, one oscillator about 10 [Verify], logic, optical modules about 20 (batch 10) [Verify] | 127 mA | 168 mA | AMS1117: 1.7 V x 0.168 A = 0.29 W |
| 4 relay coils, G6K-2F-Y 5 V: 21.1 mA each (237 ohm) | 84 mA | 84 mA | distributor listings of Omron's figures [Verify]; 42 mA if line 3/4 not fitted |
| **Total** | **557 mA** | **650 mA** | TPS563208 3 A |

**Through 5V_EXT the Nucleo takes about 400 mA of its 500 mA limit (UM2408 Table 6): 80 %, an
estimate until measured.** If the measurement says otherwise, the panel's 3.3 V moves to its own
LDO (with care over back-powering the MCU's pins).

12 V input, at a buck efficiency of 90 % (5 V) and 88 % (5.5 V) [Verify on the bench]:

| | 5V_DIG | 5V_ANA path | +/-15 V module | **12 V total** |
|---|---|---|---|---|
| Worst case | 3.6 W | 1.3 W | 3.4 W | **8.3 W, 0.69 A** |
| Typical, full-scale signal | 3.1 W | 1.0 W | 1.8 W | **5.9 W, 0.49 A** |
| Idle | 3.1 W | 1.0 W | 1.1 W | **5.2 W, 0.43 A** |

Adapter: 12 V regulated, at least 1.5 A (18 W), class II (unearthed) preferred (section 7), plug
and polarity to match the chosen DC jack [Verify]. PTC: hold current at least 1.0 A [Verify part
in stage 3]. About 5 to 8 W of heat inside the case; the PCM3168A alone dissipates 1.2 W through
its PowerPAD into the plane (21 C/W, SBAS452A 8.4).

## 6. How the Nucleo is fed (SPEC V7)

From UM2408 Rev 6, section 7.4:

- **Through 5V_EXT, CN11 pin 6 (morpho only), 4.75 to 5.25 V, 500 mA maximum, with jumper JP2 on
  pins 5-6 "EXT"** (7.4.3, Table 6). This is the one external input that suits a 5 V rail.
- Not VIN (CN8 pin 15 or CN11 pin 24): 7 to 11 V only, and only 250 mA input current between 9
  and 11 V (Table 5). 12 V is out of range.
- Not 3V3_EXT (CN8 pin 7 / CN11 pin 16 as an input): the ST-LINK would be unpowered and debugging
  lost (7.4.5).
- **Order when debugging (7.4.6):** JP2 on 5-6, power from 12 V first, check LD5 is on, then plug
  the ST-LINK USB cable. Plugging the ST-LINK first risks the board being powered from the PC at
  its 300 mA enumeration limit. This becomes a bring-up rule and a label on the board.
- The 3V3 pin (CN11 pin 16) then serves as an output for the panel (up to U11's 1300 mA, 7.4.7);
  the Nucleo's 5V pin (CN11 pin 18) is left unconnected.
- **This forces the morpho rows**: 5V_EXT exists on CN11 only. The main board therefore meets the
  Nucleo on both morpho rows (CN11, CN12), which also gives every MCU pin (pin plan). Male headers
  must be soldered into the Nucleo's empty CN11 and CN12 footprints (7.17: "OFF by default"). That
  is work on the Nucleo, so it needs the owner's go (CLAUDE.md) [owner decides].
- Changing JP2 from 1-2 (STLK, the default) to 5-6 is a jumper move, not a rework, but the board
  then no longer starts from the ST-LINK cable alone. For bench work without the main board, the
  owner moves it back.

## 7. Grounding

**One ground plane per board, no splits; separation by placement.** Main board stack-up: signal,
ground, power, signal (layer 2 unbroken under the converter and analogue stages).

Zones on the main board (top view, rear edge at the back; detail in `mechanical_interface.md`):

| Zone | Where | Contents |
|---|---|---|
| Power | rear left | DC entry wiring, protection, both bucks, the module, their LC filters |
| Digital | left and centre, above the Nucleo | morpho sockets, USB-C path, optical, clock select and buffer |
| Converter | centre, at the digital/analogue boundary | PCM3168A (digital pins facing the Nucleo, analogue pins facing the right), its LDO and 3.3 V |
| Analogue | right half | input stages, output stages, relays, OPA1622, ±12 V LDOs, rear TRS jacks |
| Panel link | front edge, right of centre | the ribbon header, headphone pins at the analogue end |

Connections:

- **Chassis strip:** a copper strip on the main board along the rear edge, separate from the
  circuit ground plane, carrying every jack sleeve, the USB-C shell, and the jacks' ESD/RF
  capacitors to chassis. It is bonded to circuit ground at **one point**: a plated mounting hole
  next to the USB-C socket and the DC entry, through a 0 ohm link (with a footprint for 10 nF in
  parallel with 1 Mohm instead, for experiments). The case is bonded at that same screw. Cable
  shield currents (sleeves) then flow in the chassis, not across the analogue plane: the "pin 1
  to chassis at the entry" practice of AES48 [Verify reference]. If the NMJ6HCD2's ferrule
  touches the sleeve, the rear panel bonds the strip to the case at every jack too; that is
  consistent (all on one edge) [Verify the ferrule, V28]. Neutrik's sheet calls it a "chrome
  ferrule" on a polyamide shell with a polyamide nut and washer, and says nothing of a ground
  contact; a meter on one sample settles it.
- **12 V return:** the DC jack's negative is circuit ground, entering at the power corner next to
  the bond point. It is not chassis.
- **USB:** the USB-C GND pins are circuit ground (the MCU's reference); the shell goes to the
  chassis strip, with an optional 1 Mohm / 4.7 nF footprint to circuit ground.
- **Nucleo:** its ground joins the main board through the morpho GND pins (CN11 8, 19, 20, 22, 49,
  60; CN12 9, 20, 39, 54, 63, AGND 32). The Nucleo must be mounted on **insulating** standoffs or
  washers [Verify whether its holes are plated to ground]: a metal standoff would make a second
  chassis bond in the middle of the board. Same for every main board hole except the bond hole.
- **Panel board:** its ground comes only through the ribbon's ground conductors. It is not bonded
  to the front panel (pot and encoder bushings are not connected to the elements [Verify]). The
  headphone return pair is not connected to the panel ground at all: it runs from the jack sleeve
  to the OPA1622's ground on the main board.
- **Ribbon grounds** join the main board's plane at the header, at the analogue end for the
  headphone pair and at the digital end for the rest.

**Ground loop through the PC.** With the monitors on mains earth and the PC on mains earth, a loop
exists: PC earth, USB cable ground, this device's circuit ground, the bond, the chassis, the
monitor cables' shields, the monitors' earth, the mains. What the design does:

1. Balanced outputs with both legs driven: the loop current flows in the cable shield, not in
   the signal pair, and the monitors' balanced inputs reject the ground difference.
2. The loop current's path on this board is short and away from the analogue zone: in at the
   USB-C GND pins, out at the bond screw next to it, then through the chassis.
3. Balanced inputs reject a ground difference to the source, up to the input stage's common-mode
   rejection (worked in `rev_a_input_budget.md`).
4. The headphones are referenced to this ground; the loop current never crosses the headphone
   amplifier's ground if (2) holds.
5. Not done: a USB isolator (a full-speed isolator such as the ADuM3160 exists; it would add a
   part, a supply and cost). It is the fallback if batch 7 measures hum that (1) to (4) do not
   remove. A class I (earthed) 12 V adapter would add a second loop; class II is preferred.
6. While debugging, the ST-LINK cable is a second ground to the PC. Lab measurements are taken
   with it unplugged.

## 8. Mute and sequencing

Hardware default is **muted**: relay coils off (their NC contacts ground the jack side of each
leg, with a 10 k bleed), OPA1622 EN pulled low (shutdown below 0.78 V referred to its GND pin,
SBOS727B 7.3.3; "designed to eliminate click and pop" on entering and leaving shutdown),
PCM3168A RST pulled low (SBAS452A 9.3.6). Every control line has a pull-down, so a reset or a
crash of the MCU (pins high-impedance) mutes.

**RAILS_OK** is an open-drain supervisor on 12V_P (threshold about 10.5 V with hysteresis, a
delay of about 200 ms after power-up [part chosen in stage 3]). Low forces both relay drivers and
the OPA1622 EN low in hardware, whatever the MCU does, and interrupts the MCU (EXTI).

**Power-up:**
1. 12 V on. Bucks soft-start in 1 ms (TPS56320x), the module and LDOs follow; the oscillator
   selected by its pull-up (24.576 MHz) runs, so SCKI is present before RST rises.
2. RAILS_OK goes high after its delay.
3. The MCU boots (5V_EXT), starts SAI1 from I2S_CKIN, releases RST, waits for the internal reset
   to finish (the OVF pin's 4096-SCKI pulse, SBAS452A 9.4.1; 3846 SCKI plus the DAC and ADC delays,
   8.7), writes and reads back the registers over I2C (#142).
4. Firmware checks: RAILS_OK high, the codec answering, the SAI running without errors. Then
   relays on (operate 3 ms max), 20 ms later OPA1622 EN high, then the DSP ramps the volume up.

**Rate change** (SPEC 6.5, and SBAS452A 12.1.12: "external mute ON, codec power-down ON, SCKI stop
and resume if necessary, codec power-down OFF, external mute OFF"): DSP ramp down, EN low and
relays off, codec power-save by register, SAI stop, enable the other oscillator, switch the mux,
disable the first, SAI start, power-save off, wait for the codec's fade-in, relays on, EN high,
ramp up.

**Power-down (12 V pulled):** RAILS_OK falls at 10.5 V; relays release within 3 ms
(G6K-2F-Y release time 3 ms max, distributor listings [Verify]); OPA1622 EN low at once. The
analogue rails must outlive that:
- 12V_P keeps the module regulating from 10.5 V down to its 9 V minimum: 1000 uF x 1.5 V /
  0.69 A = 2.2 ms at the worst-case load;
- then the 220 uF per rail carries the LDOs from 15 V down to their 12.3 V minimum input:
  220 uF x 2.4 V / 90.5 mA = 5.8 ms (worst load), 10.8 ms (typical).
- Total about 8 ms against a 3 ms release: margin about 5 ms at the worst load. Bring-up step 4
  measures it.
- The firmware, on the RAILS_OK interrupt, stops writing flash and mutes in the DSP; the
  Nucleo's own 5 V lasts as long as 12V_P stays over 4.5 V.

## 9. Protection

| Connector | Protection |
|---|---|
| 12 V DC | PTC (hold at least 1.0 A); reverse polarity: high-side P-FET with a gate-source zener; over-voltage cut-off: a second P-FET switched off by a TL431-based detector above about 16 V (the TPS563208 is rated to 17 V input, the module to 18 V); SMBJ15A TVS after the switches for transients [all values Verify in stage 3, simulate the cut-off]. A 19 V laptop adapter then switches the device off instead of destroying it. Runner-up: an eFuse with over-voltage and reverse protection [Verify part] |
| Line inputs | Per leg: about 100 ohm series and 470 pF to chassis (RF filter, corner well above audio with the source impedance), a bidirectional TVS with at least 15 V stand-off (a +20 dBu unbalanced signal peaks at 10.96 V on one leg), then the coupling capacitor and the stage's input resistor (`rev_a_input_budget.md`) |
| Monitor and line outputs | 100 ohm build-out per leg (also limits a short to a TS plug's sleeve: the OPA1678 is short-circuit protected at about 50 mA, SBOS855E), relay, bidirectional TVS at least 15 V stand-off at the jack, 10 k bleed. A TS plug in an output shorts the cold leg through 100 ohm: the level drops 6 dB, nothing breaks |
| Headphones (panel) | Low-capacitance bidirectional TVS at least 12 V stand-off on tip and ring to the return, at the jack; 1 ohm build-out at the amplifier; the OPA1622 limits at +145 / -130 mA and shuts down thermally (SBOS727B 7.3.2) |
| USB-C | USBLC6-2SC6 on D+, D- and VBUS, next to the socket [Verify JLC class] |
| Optical | none needed (no galvanic path) |
| Panel controls | metal bushings to the front panel (chassis); every ribbon line has a series resistor at the MCU end and the MCU's clamps |

**DC blocking:** input coupling capacitors; the DAC outputs are AC-coupled into every stage (they
sit at 2.5 V); the outputs themselves are DC-coupled with under about 1 mV of offset (OPA1678
offset times a DC gain of 1, the input being AC-coupled), so no output capacitors.

## 10. USB-C (SPEC V13)

- **Socket:** GCT USB4105-GF-A, LCSC C3020560 (snapshot: 515 in stock, about $1.05 at 1, seen
  2026-11-18). Digi-Key lists its mounting as "surface mount, right angle; through hole", the
  through-hole part being the shell stakes; LCSC calls it SMD [Verify the drawing: V26].
- **CC:** 5.1 kohm to ground on CC1 and CC2, separately (a device port; #78).
- **VBUS:** sensing only, never a supply. VBUS through a 100 k / 200 k divider (5 V to 3.3 V) to
  PE15, a 5 V-tolerant pin [Verify FT and its behaviour unpowered: the divider limits any
  injection to under 50 uA]; 1 uF on VBUS at most.
- **Data pair:** USBLC6-2SC6 at the socket, then a 90 ohm pair to CN12 pin 12 (PA12, D+) and pin 14
  (PA11, D-). Length about 80 mm on the main board plus the Nucleo's own trace [Verify in layout],
  matched within 2 mm, no vias where avoidable. No series resistors (the OTG_FS PHY is internal
  [Verify RM0399]). Full speed (12 Mb/s, rise times 4 to 20 ns) tolerates the header.
- **Nucleo solder bridges** (UM2408 Table 16 and Table 13): SB26 (PA12) and SB27 (PA11) connect
  the MCU pins to the Nucleo's own micro-AB socket CN13 when ON (the default); OFF leaves them on
  the morpho only. SB21 connects PA9 to CN13's VBUS circuit.
  - **Option A, no rework (proposed first):** leave all three as shipped. CN13 and its ESD part
    become a stub of a few cm on the bus, which full speed tolerates [Verify by the batch 7
    enumeration and soak]. CN13 must never be used at the same time. VBUS is sensed on PE15, not
    PA9; the firmware turns the OTG peripheral's VBUS sensing off and uses PE15 for
    attach/detach [Verify in batch 4's USB stack].
  - **Option B, rework:** open SB26 and SB27 to remove the stub. Only if A fails, and only with the
    owner's go.
  - [Verify] that CN12 pin 12 ("PA12 or NC" in Table 19) and pin 14 ("PA11 or PE6") carry PA12 and
    PA11 as shipped: a continuity check on the owner's unpowered board, MCU pin to header pin.
- **Fallback:** a short internal lead from CN13 (micro-AB) to a panel-mount USB-C socket on the
  rear panel [Verify a part], with the main board's USB-C footprint left empty.
- The UM2408 warning (7.11) that a cable in CN13 before the board is powered can inject current
  into the MCU applies to the main board's socket too: with Option A the host's D+/D- are
  connected to an unpowered MCU when 12 V is off. A host does not drive D+/D- before attach, so
  the risk is ESD-level only [Verify].

## 11. Panel interface

### 11.1 Ribbon pin-out (2 x 20, 2.54 mm, shrouded, 40-way IDC; conductor n = pin n)

| Pin | Signal | Group | | Pin | Signal | Group |
|---|---|---|---|---|---|---|
| 1 | HP_L | phones | | 21 | GND | |
| 2 | HP_L_RET | phones | | 22 | LED1 input 1 signal | LEDs |
| 3 | HP_R_RET | phones | | 23 | LED2 input 1 clip | LEDs |
| 4 | HP_R | phones | | 24 | LED3 input 2 signal | LEDs |
| 5 | GND | | | 25 | LED4 input 2 clip | LEDs |
| 6 | POT_REF (VREF+) | pots | | 26 | LED5 mute | LEDs |
| 7 | POT1 bass | pots | | 27 | LED6 dim | LEDs |
| 8 | POT2 mid | pots | | 28 | LED7 FX on | LEDs |
| 9 | POT3 treble | pots | | 29 | PANEL_3V3 (LED anodes, OLED, encoders) | supply |
| 10 | POT4 monitor | pots | | 30 | GND | |
| 11 | POT5 phones | pots | | 31 | ENC1_A | encoders |
| 12 | POT6 FX amount | pots | | 32 | ENC1_B | encoders |
| 13 | POT7 blend | pots | | 33 | ENC1_SW | encoders |
| 14 | POT_GND | pots | | 34 | ENC2_A | encoders |
| 15 | GND | | | 35 | ENC2_B | encoders |
| 16 | BTN1 FX select | buttons | | 36 | ENC2_SW | encoders |
| 17 | BTN2 FX on | buttons | | 37 | GND | |
| 18 | BTN3 tap | buttons | | 38 | I2C4_SCL (OLED) | display |
| 19 | BTN4 mute | buttons | | 39 | I2C4_SDA (OLED) | display |
| 20 | BTN5 dim | buttons | | 40 | GND | |

- The phones group sits at the cable's edge (pin 1, the red stripe), so it has one neighbour, a
  ground. Each headphone signal is next to its own return.
- Six grounds between groups, plus a dedicated pot ground (pin 14) and the two headphone returns.
- No spare pins. Reading the pots through a multiplexer would free three; not needed (11.2).
- The LED current returns through the LED lines into the MCU's pins (sink drive), not through the
  ribbon's grounds; the switches carry no current to speak of. So the shared grounds carry almost
  nothing, which is what keeps the pot readings and the panel clean.
- Ribbon length about 150 mm; 28 AWG conductors about 0.22 ohm/m [Verify], so 33 mohm each.
- Stage 3's script checks both netlists against this table.

### 11.2 Pots: seven ADC pins, no multiplexer (SPEC V12)

Seven ADC1 inputs are free of conflicts on the morpho rows (PA3, PC0, PA4, PA5, PA6, PB1, PF11;
`pin_plan.md`). One ADC scans all seven by DMA, matching `ctl_pot`'s 16-sample sums. A
multiplexer would add a part, settling time and switching charge for three ribbon pins we do not
need.

- **Reference:** pot tops on POT_REF, wired from the Nucleo's VREFP pin (CN12 pin 7); bottoms on
  POT_GND, wired to the Nucleo's AGND pin (CN12 pin 32). Ratiometric: the ADC's reference and the
  pot top are the same node, so supply drift cancels. Not filtered: an RC in the reference would
  make the pot top differ from VREF+ at exactly the frequencies the filter acts on. Load: 7 x 10 k
  in parallel = 1.43 kohm, 2.3 mA.
- **Wiper filter:** 10 nF at the pot (panel side) against ribbon pickup; at the MCU end 1 kohm in
  series and 100 nF to POT_GND (corner 1.6 kHz, settles in under 1 ms against `ctl_pot`'s 4 ms
  smoother). The 100 nF is also the ADC's charge reservoir: its sampling capacitor (a few pF)
  disturbs it by under 1e-4, 0.2 LSB at 12 bits [Verify the H7's sampling capacitance].

### 11.3 Buttons and encoders

Switches to the panel ground. At the MCU end: 10 k pull-up to the Nucleo 3V3, 1 k series, 10 nF at
the pin (a 10 us edge on press, about 110 us on release); `ctl_button`'s 5 ms integrating
debounce does the rest. Encoders the same with 1 nF, into TIM3 and TIM4 in encoder mode with the
timers' input filters; their push switches as buttons. Pull-ups on the main board, so the panel
board carries only switches.

### 11.4 LEDs

GPIO with PWM, no driver: each LED and its resistor on the panel from PANEL_3V3 to its ribbon
line; the MCU pin sinks (timer channel, active low). 2 to 3 mA with high-efficiency diffused 3 mm
LEDs; 7 x 3 mA = 21 mA total [Verify the H7's per-pin and total limits in DS12919]. PWM above
20 kHz with the slowest GPIO speed setting, so neither the PWM frequency nor fast edges reach the
audio band or the ribbon's neighbours.

At 3.3 V only colours with a low forward voltage work well (red, amber, yellow, yellow-green, about
1.8 to 2.2 V): R = (3.3 - 2.0) / 2.5 mA = 520 ohm. The sketch's blue FX-on LED (forward voltage 2.8
to 3.2 V) would get an ill-defined current. **Either the FX-on LED is amber or yellow-green, or it
gets a transistor and a 5 V anode supply** [owner chooses the colours].

### 11.5 OLED and encoders (batch 11)

A 2 x 5 header on the panel board carries I2C4 (SDA, SCL), PANEL_3V3, GND and nothing else; the
encoders are footprints on the panel board. I2C4, not the codec's I2C1, so the ribbon's
capacitance and pickup stay off the converter's control bus. Pull-ups 4.7 k at the MCU end;
100 kHz is enough for an OLED of 128 x 64 at a few frames per second [Verify the module].

## 12. Headphone amplifier: main board or panel board

| | **A. On the main board** (line level stays on the main board; 0.7 V, 26 mA peak over the ribbon) | **B. On the panel board** (DAC 3/4 legs over the ribbon, OPA1622 at the jack) |
|---|---|---|
| Ribbon pins | 4: two signals, two dedicated returns | 4 signal legs, +12 V, -12 V, EN, plus their grounds: 7 to 9 |
| Current in the ribbon | the headphone current, in its own pair | the amplifier's supply current, returning in shared grounds |
| Pickup from digital lines | the lines are driven from about 1 ohm: capacitive pickup of a few pF from conductors 15 or more away is negligible | the legs come from the DAC's pins through filter resistors (kohm level): more sensitive; balanced, so common-mode pickup is rejected by the difference stage's resistor match (about 40 dB with 1 % parts) |
| Ground return | the headphone current returns to the amplifier on its own pair; only the sleeve contact is common | short and local at the panel, but the amplifier's rail current flows back through the ribbon's grounds: half-wave signal currents of up to 26 mA in the grounds the pots and LEDs share |
| Crosstalk (section 4.3) | about -64 dB (sleeve plus the paralleled returns) | about -66 dB (sleeve plus a short trace) |
| Mute and power-fail | EN and RAILS_OK local to the amplifier | EN and the rails cross the ribbon |
| Heat, rails | on the main board next to the ±12 V LDOs | ±12 V on the ribbon, a second set of decoupling |
| Part count | lowest | more decoupling, a second analogue zone on a 2-layer panel board |

**Proposed: A, on the main board.** Priorities 1 and 2 (correctness, robustness) drive it: the
analogue rails, the mute and the power-fail path stay on one board; the ribbon carries no supply
current in shared grounds; the panel board stays a digital and passive board that can be 2
layers. The only thing B wins is about 2 dB of crosstalk that the TRS jack limits anyway.

**Condition for A:** the headphone jack's sleeve must not touch the front panel, or headphone
current would also return through the case. The decided NMJ6HCD2 is a horizontal PCB jack and
would point sideways on a panel board that is parallel to the front panel; a vertical-mount jack
is needed there anyway. Proposed: **Neutrik NJ6FD-V**. Its technical sheet (Neutrik, 18.11.2026):
vertical PCB mount, three switching contacts (T/TN/R/RN/S/SN), plastic body (POM, cap PA 6.6),
12 mm chassis hole, contact resistance under 10 mohm initial, **panel thickness 1.2 to 1.5 mm**.
The plastic body isolates the sleeve from the panel, which is what option A needs, but **the 2 mm
front panel is too thick for it.** Two ways: the owner machines a spot face on the panel's rear,
1.5 mm thick, about 20 mm across, round the phones hole (the case is his CNC work anyway); or a
vertical jack rated for 2 mm is found [Verify a part]. The drawing (height above the PCB) is not
in the sheet [Verify]. This replaces NMJ6HCD2 for the phones only [owner decides: it changes a
stage 1 decision for one jack, and needs the spot face].

## 13. Board sizes and JLC price steps

- **The rear edge does not fit 160 mm.** Power switch, DC jack, USB-C, two optical modules and six
  TRS jacks (line in 1, 2, monitor L, R, line out 3, 4): the NMJ6HCD2 is 18.2 mm wide (LCSC
  attributes) and needs about 20.5 mm pitch for plug bodies, so 6 jacks take 121 mm; the other
  five items about 62 mm; with edge margins about 192 mm. **Proposed main board: 200 x 100 mm**
  (case about 210 x 55 x 140 mm). Positions in `mechanical_interface.md`. The alternative is to
  drop or move something decided: line outputs 3 and 4 (the owner's decision), or the power
  switch to the front panel (still about 170 mm).
- **Panel board: 160 x 46 mm, 2 layers** (46 not 52 mm: a 55 mm case with 2 mm walls has about
  51 mm inside, section 3 of the mechanical note). It needs no analogue stage with option A.
- **JLC pricing:** 4-layer prototypes have a special low price up to 100 x 100 mm; above that the
  price is by area plus fixed fees [Verify on the live quote]. No current per-area figure was
  readable today: JLC's notices of June and August 2026 announce price changes without numbers
  and point to the instant quote, which is script-rendered. Area for 5 boards: main 200 x 100 mm =
  0.10 m2 (160 x 100 would be 0.08 m2, so +25 % on the area-dependent part); panel 160 x 46 mm on
  2 layers = 0.037 m2. Neither board can be brought under 100 x 100 mm with these connectors and
  controls, so the step is paid either way; the width choice costs the area difference only. The
  owner reads three quotes (4 layers, 1.6 mm, HASL lead-free, 5 pcs): 100 x 100, 160 x 100, 200 x
  100, plus the panel on 2 layers [V21].
- JLC assembly: Extended parts each carry a loading fee per order [Verify at stage 5].

## 14. Test points

- **Rails:** 12V_IN (before protection), 12V_P, 5V_DIG, 3V3_DIG, 5V5_PRE, 5V_ANA, +15 and -15 raw,
  +12 and -12 analogue, Nucleo 3V3, VREFP; each regulator's output through a 0 ohm link or solder
  jumper so it can be brought up unloaded; ground posts at the power corner and in the analogue
  zone.
- **Clocks:** each oscillator output, the mux output, SCKI at the converter, I2S_CKIN at the
  header.
- **TDM and control:** BCK, LRCK, DIN1, DOUT1 (and DOUT2, DIN2 as pads only: section 15 note), SCL,
  SDA, RST, OVF, MODE.
- **Mute and power:** RAILS_OK, each relay coil, OPA1622 EN.
- **Analogue:** each DAC pin used (before the stages), each stage output before the relay, each ADC
  input pin pair, the headphone output.
- **Recovery:** a 2-pin header from BOOT0 (CN11 pin 7) to 3V3, fitted open: the SMPS-mismatch
  recovery (UM2408 7.4.8, PROGRESS batch 1) needs BOOT0, and the Nucleo is buried under the main
  board.

## 15. Bring-up order for batch 7

0. **Before the boards arrive:** the owner measures the Nucleo's 5 V current with the present
   firmware (a USB power meter on the ST-LINK cable): checks the 300 to 350 mA estimate (V29).
1. Main board without the Nucleo, every rail link open, bench supply at 12 V limited to 200 mA:
   reverse the supply (limit 50 mA) and check nothing conducts; raise it slowly to 17 V and check
   the cut-off trips near 16 V; bucks and module unloaded: voltages and ripple (20 MHz bandwidth).
2. Close the links one at a time: each LDO, then its loads. Voltages, ripple, temperatures.
3. RAILS_OK: rising delay, falling threshold.
4. **Power-fail timing:** pull 12 V and scope RAILS_OK, a relay coil and both ±12 V rails: the
   relay must open (coil current gone plus 3 ms) before either rail leaves regulation.
5. JP2 to pins 5-6, mount the Nucleo on its insulating standoffs, 12 V on, then the ST-LINK cable
   (UM2408 7.4.6). Flash, console. Measure the 5V_EXT current.
6. Clocks: frequency, duty and ringing of each oscillator at SCKI and at PC9; the switch-over.
7. Converter control: release RST, see the OVF pulse, read the registers over I2C, write and read
   back (#142).
8. SAI1 TDM at 48 kHz: the logic analyser on BCK, LRCK, DIN1, DOUT1; ADC inputs shorted give
   zeros; a -20 dBFS DAC tone at the DAC test pads, then at the stage outputs into a dummy load
   with the relays open.
9. Relays closed, outputs into dummy loads at -20 dBFS (the owner is told first, CLAUDE.md); then
   inputs from a generator; then the headphone output into 38 ohm.
10. Panel board over the ribbon: every pot's full travel and reading noise, every button and LED,
    then nothing from the ribbon audible at full monitor volume.
11. USB through the USB-C socket: enumeration, then the batch 4 duplex soak (Option A first).

Note for rev B: the PCM3168A's TDM format at 96 kHz uses two data lines each way (DOUT1/2, DIN1/2
at BCK 128 fs; SBAS452A Table 11), or the high-speed TDM format for the DAC only (DIN1 at 256 fs).
Rev A runs at 48 kHz (decision of 2026-11-17), where one line each way is right; DOUT2 and DIN2
get test pads only (DIN2 tied low through 10 k). V20 is corrected accordingly.

## 16. Parts newly picked in this stage

| Part | Use | LCSC | Seen 2026-11-18 |
|---|---|---|---|
| TPS563208DDCR | both bucks | C468250 | snapshots: 75 160 in stock from $0.076; 1820 at $0.145 (5+) |
| WRA1215S-3WR2 (YLPTEC) | ±15 V | C5369659 | page: 9 to 18 V, 100 mA, 220 uF max load; snapshot stock 210; price not shown |
| TPS7A2050PDQNR | 5V_ANA | C2866499 | snapshot 650 in stock; SOT-23-5 version not found at LCSC |
| AMS1117-3.3 | 3V3_DIG | C6186 [Verify] | not read |
| USB4105-GF-A | USB-C | C3020560 | snapshot 515 in stock, about $1.05 |
| Neutrik NJ6FD-V | phones jack | not found | Neutrik sheet read: panel 1.2 to 1.5 mm |
| RK09L1140A5L | pot (stage 1) | C7419101 | page reached, no price; Digi-Key lead time 24 weeks |

Price and stock fields on the LCSC and JLC pages are drawn by script and were not visible to the
fetch; V21 stays open for every part.

## 17. What the owner decides before stage 3

Listed with the PROGRESS entry of 2026-11-18 and in the report; the same list:

1. 0 dBFS: +20 dBu in, +18 dBu out, headphones about 110 dB SPL (section 3), and his monitors'
   maximum input level.
2. TPS563208 instead of TPS563201 (5.1).
3. TPS7A2050 for the converter's 5 V from a 5.5 V buck (5.2), and the X2SON package or the
   runner-up.
4. The 3 W wide-input module WRA1215S-3WR2 instead of the 2 W (5.3).
5. Morpho mounting and soldering male headers into CN11 and CN12; JP2 to 5-6 (section 6).
6. USB Option A (no rework) first; the CN12 pin 12/14 continuity check (section 10).
7. Headphone amplifier on the main board, and the NJ6FD-V for the phones jack with a 1.5 mm
   spot face in the front panel (section 12).
8. Line outputs 3 and 4 from DAC 5 and 6 (section 2).
9. Main board 200 x 100 mm, case about 210 wide; panel board 160 x 46 mm, 2 layers (section 13).
10. LED colours (11.4).
11. The ribbon pin-out (11.1).
12. Insulating standoffs for the Nucleo and the single chassis bond (section 7).
13. Measure the Nucleo's current (bring-up step 0) and, with calipers, the heights listed in
    `mechanical_interface.md` (V14).

## 18. Sources

- TI PCM3168A datasheet SBAS452A: https://www.ti.com/lit/ds/symlink/pcm3168a.pdf
- TI OPA1622 SBOS727B: https://www.ti.com/lit/ds/symlink/opa1622.pdf
- TI OPA167x SBOS855E: https://www.ti.com/lit/ds/symlink/opa1678.pdf
- TI TPS7A49 SBVS121E: https://www.ti.com/lit/ds/symlink/tps7a49.pdf
- TI TPS7A30 SBVS125D: https://www.ti.com/lit/ds/symlink/tps7a30.pdf
- TI TPS56320x: https://www.ti.com/lit/ds/symlink/tps563201.pdf
- ST UM2408 Rev 6, STM32H7 Nucleo-144 boards (MB1363)
- [LCSC WRA1215S-3WR2 C5369659](https://lcsc.com/product-detail/Isolated-Power-Modules_YLPTEC-WRA1215S-3WR2_C5369659.html);
  [LCSC A1215S-2WR3 C48888070](https://www.lcsc.com/product-detail/C48888070.html);
  [JLC C48888070](https://jlcpcb.com/partdetail/C48888070)
- [LCSC TPS563208DDCR C468250](https://www.lcsc.com/product-detail/C468250.html)
- [LCSC TPS7A2050PDQNR C2866499](https://www.lcsc.com/product-image/C2866499.html);
  [Digi-Key TPS7A2050PDBVR](https://www.digikey.co.uk/en/products/detail/texas-instruments/TPS7A2050PDBVR/13566862)
- [LCSC USB4105-GF-A C3020560](https://www.lcsc.com/product-detail/C3020560.html);
  [Digi-Key USB4105-GF-A](https://www.digikey.ca/en/products/detail/gct/USB4105-GF-A/11198441)
- [Neutrik NMJ6HCD2 product page](https://www.neutrik.com/product/nmj6hcd2);
  [LCSC NMJ6HCD2 C368502](https://www.lcsc.com/product-detail/C368502.html);
  [Neutrik NJ6FD-V (Buerklin)](https://www.buerklin.com/en/p/neutrik/phono-connectors/nj6fd-v/39F1641/)
- [Omron G6K-2F-Y DC5 (Digi-Key)](https://azcus.digikey.com/en/products/detail/omron-electronics-inc-emc-div/G6K-2F-Y-TR-DC5/369212)
- [JLC price notice, August 2026](https://jlcpcb.com/news/jlcpcb-fr4-pcb-price-adjustment-august2026)
