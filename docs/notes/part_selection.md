# Rev A part selection (batch 5, stage 1)

Written 2026-11-18. This is stage 1 of batch 5 (`docs/PLAN_BATCHES.md` section 7): candidates,
the figures that separate them, and a recommendation with a runner-up for each part. Stage 2
(architecture: levels, noise budget, power tree, grounding, pin map) starts only after the owner
has signed this off, and after his exercise: the input stage's noise and level budget, worked by
hand from the chosen parts' datasheets. So this note gives full-scale levels and noise only as
datasheet figures, and does not work the budget.

## 0. How far the figures can be trusted

- **Prices and stock are not live.** Direct queries to the LCSC and JLC part pages were refused
  in this session, so every price and stock figure below is a snapshot from a search index:
  undated, and sometimes two snapshots of one page disagree (both are given then). Each carries
  "seen 2026-11-18 (snapshot)". The owner checks them live before stage 2 is signed off, or
  allows a direct query [Verify: SPEC V21 proposed].
- **JLC part class.** JLC's own listings were seen for two parts only (both Extended). Every other
  part is assumed Extended until a live check says otherwise; nearly every part on this board is
  a specialist audio or power part, so few will be Basic. Each Extended part costs a loading fee
  per order [Verify the fee on the live quote, stage 5].
- **Datasheet figures** are from the manufacturers' product pages and datasheets where the search
  reached them, otherwise from distributor summaries, which are marked. Typical values, A-weighted,
  at 48 kHz unless stated.

## 1. From the transcripts

Read in full for this stage: "Mini 6-Layer Mixed-Signal Hardware Design Walkthrough" (#78) and
"How To Write A Driver (Audio CODEC & I2C)" (#142). What carries over, and what does not:

- **Software (register) control over hardware strapping** (#142): choose a converter with an I2C
  or SPI control port and a reset pin driven by the MCU, held in reset by a pull-down until the
  rails are stable. Every candidate below has both. Strapping only stays as a fallback.
- **Reset and sequencing:** the converter is held in reset until the supplies are stable, then the
  clocks start, then it is configured, then powered up. Some converters power down without a
  master clock, and some must be powered down before a configuration change (#142). This feeds
  the stage 2 mute and sequencing design; it also argues for a converter whose datasheet states
  the power-up order clearly.
- **Codec as clock slave:** the DSP or oscillator supplies MCLK, BCLK and LRCLK; a crystal
  oscillator rather than the MCU's internal oscillator, for jitter and accuracy (#142). This
  project already has the oscillators as master (SPEC 6.3).
- **Supplies near the analogue section are linear** (#78): the video's board uses only LDOs, plus
  an RC filter (10 ohm, 47 uF) to make a quiet analogue 5 V from the digital 5 V. Here the 12 V
  input forces at least one switching converter (5 V for the Nucleo, and the split rails), so the
  lesson becomes: switchers in one corner, LDOs after them, and the converter's analogue supply
  from its own low-noise LDO.
- **Low supply forced the op-amp choice** (#78): with a 5 V analogue rail the video needs
  rail-to-rail CMOS op-amps biased at half supply. This board has split rails, so ordinary audio
  op-amps work and the line levels in SPEC 3.3 are reachable.
- **Input and output protection pattern** (#78): ESD diode, an RF filter (series R, shunt C, corner
  around a few hundred kHz to 1 MHz) before any semiconductor, a high-value bias resistor, coupling
  capacitor; on the output, 100 ohm build-out to isolate the op-amp from cable capacitance, a
  coupling capacitor and bleed resistor, ESD. Parts for these are commodity and not listed here.
- **Series resistors (33 ohm) at clock sources** (#78) to reduce ringing and EMI: the oscillator
  outputs and the clock buffer get them.
- **One 100 nF per supply pin plus a bulk capacitor** near each IC (#78).
- **Not carried over:** the CS4270 (stereo only, two in and two out: this device needs four
  outputs), the 6-layer impedance-controlled stack-up (this board is 4 layers and has no SDRAM or
  ULPI), the mid-mount USB-C (rear panel, data only here).

## 2. What the converter must do

From SPEC 3.1, 3.3 and 6.3:

- 2 analogue inputs, 4 analogue outputs (monitor pair, headphone pair), 24 bit.
- 44.1, 48, 88.2 and 96 kHz, as a clock slave to the oscillator's MCLK (22.5792 or 24.576 MHz).
- One TDM bus to one SAI on the H755: ideally one data line each way.
- Control by I2C or SPI, and a reset pin.
- Analogue targets (mid-grade, measured honestly): dynamic range 105 dB or better A-weighted, in
  and out; THD+N -90 dB or better at -1 dBFS; crosstalk -90 dB or better.
- JLC can assemble it (exposed pads and QFN are fine for their reflow; hand-solderability only
  matters for a rework).

## 3. Converter candidates

| | PCM3168A (TI) | AK4619VN (AKM) | CS42448 (Cirrus) | AD1939 (ADI) | PCM1863 + 2 x PCM5122 (TI) |
|---|---|---|---|---|---|
| Channels in / out | 6 / 8 | 4 / 4 | 6 / 8 | 4 / 8 | 2 / 2+2 |
| ADC dynamic range | 107 dB differential (104 single-ended) | 106 dB S/N, differential, 48 kHz | 105 dB differential | 107 dB | 110 dB differential (106 single-ended) |
| DAC dynamic range | 112 dB (differential, 48 kHz) | 108 dB S/N, 48 kHz | 108 dB differential | 112 dB (distributor summary) | 112 dB [Verify] |
| THD+N | DAC -94 dB; ADC [Verify, about -93 dB] | ADC THD -95 dB (distributor guide, conditions not given) | -98 dB differential | [Verify] | [Verify] |
| Higher rates | ADC to 96 kHz, DAC to 192 kHz | to 192 kHz; ADC S/(N+D) quoted 99 dB at 96 kHz (summary) [Verify] | to 192 kHz | to 192 kHz | to 192 kHz [Verify] |
| TDM | Yes: 8 DAC channels on one pin, 6 ADC channels on one pin | Yes (frame modes not confirmed) | Yes; BCLK must be 256 fs in TDM | Yes, including dual-line | PCM1863 yes; PCM5122 by its TDM/DSP format with a slot offset |
| Full scale | In: 0.4 x VCCAD rms differential = 2.0 Vrms at 5 V. Out: 1.6 x VCCDA Vpp differential = 8 Vpp at 5 V | In: about 0.858 x AVDD Vpp differential, about 2.83 Vpp at 3.3 V (summary, garbled) [Verify] | [Verify] | [Verify] | In 2.1 Vrms at 3.3 V; out 2.1 Vrms single-ended, ground-centred [Verify] |
| Supplies | 5 V analogue, 3.3 V digital | 3.0 to 3.6 V analogue, 1.7 to 3.6 V digital, internal LDO for the core | 3.3 or 5 V (sources disagree) [Verify] | 3.3 V [Verify] | 3.3 V each |
| Package | HTQFP-64, 10 x 10 mm, exposed pad | QFN-32, 5 x 5 mm, 0.5 mm pitch, exposed pad | LQFP-64 | LQFP-64 | TSSOP-30 + 2 x TSSOP-28 |
| LCSC part, price, stock (seen 2026-11-18, snapshot) | C529289 (PCM3168APAPR): from $3.91, 483 in stock (another snapshot $5.17); JLC lists C1521535 (PCM3168APAP) | C3034747: $4.40 at 1, $3.01 at 100, 312 to 314 in stock (another snapshot $6.01); Digi-Key lead time 22 weeks | C1521507 (-DQZ): $10.44 at 1, one page out of stock; C2151089 (-CQZR) $10.51 | Not found at LCSC; distributors $11.23 at 1 | C529569 (PCM1863DBTR) $1.18, 150 in stock (JLC: 15 orderable, $2.90); PCM5122PWR C962071 out of stock, -PW tube C1540085 67 in stock at $2.99 |
| JLC class | Extended (assumed) | Extended (assumed) | Extended (assumed) | n/a | Extended (seen for PCM1863DBTR) |

Notes on the table:

- PCM3168A figures are from TI's product page and datasheet SBAS452A. AK4619VN figures are from
  AKM's product brief and datasheet as quoted by the search; the ADC figure is S/N, which AKM
  quotes where others quote dynamic range [Verify the dynamic-range row in the datasheet].
- AD1939 and the separate-pair option are listed because the plan asks for "a separate ADC with
  DACs" and the search found AD1939 in the same class as the PCM3168A. Neither wins on anything
  that matters here: the AD1939 is not stocked at LCSC, and the separate pair needs three control
  addresses, three sets of supplies and decoupling, single-ended DAC outputs (the balanced monitor
  outputs would need a differential conversion stage), and its DAC is out of stock on the reel.

## 4. Converter recommendation

**Recommended: PCM3168A.** Runner-up: AK4619VN.

The deciding numbers:

1. **DAC dynamic range 112 dB against 108 dB.** The DACs feed the monitors and the headphones,
   which is what the owner listens to every day. 112 dB leaves 7 dB above the 105 dB target for
   the output stages' noise; 108 dB leaves 3 dB, which the output driver alone can use up
   [the actual margin is the stage 2 noise budget].
2. **ADC dynamic range 107 dB differential, with an ADC full scale of 2.0 Vrms differential at
   5 V.** The AK4619VN's full scale at 3.3 V is about a third lower in voltage (about 2.83 Vpp,
   roughly 1 Vrms, [Verify]), so the input attenuator must drop the +20 dBu input further, which
   moves the attenuator's own noise closer to the converter's floor. The owner's exercise works
   this out; the larger full scale can only help.
3. **8 outputs and 6 inputs on one data line each way, at about $4 against about $4.40.** The
   spare four DAC channels keep outputs 3 and 4 as balanced line outputs possible later (the
   active crossover question in `shield_outline.md` section 8, question 5) without a second part.

What it costs over the AK4619VN:

- A 5 V analogue rail and a 3.3 V digital rail, against a single 3.3 V for the AK4619VN; the
  5 V analogue LDO must be sized for its analogue current [Verify the current: SPEC V23 proposed].
- A larger package (HTQFP-64 against QFN-32) and more decoupling.
- Twice the power, so a little more heat near the analogue section [Verify].

Why the AK4619VN is the runner-up and not rejected: it has exactly the channel count needed,
the lowest part count (one supply, no 5 V analogue LDO), the smallest footprint, and was the
cheapest stocked part with stock in the hundreds. If the owner prefers a simpler board over
4 dB of DAC margin, it is the choice, and stage 2 would then check its 96 kHz ADC figure
(99 dB quoted S/(N+D) at 96 kHz in one summary) against the target [Verify].

Rejected: CS42448 (lower dynamic range than the PCM3168A at about 2.5 times the price, patchy
stock), AD1939 (not at LCSC), the separate pair (above).

**Must be checked before the schematic (stage 3):**
- TDM at 96 kHz on the PCM3168A: 8 DAC slots and 6 ADC slots each on one line, BCLK 256 fs =
  24.576 MHz at 96 kHz, and the H755's SAI receiving and sending at that bit clock [Verify: SPEC
  V20 proposed]. If the ADC side cannot run TDM at 96 kHz, the fallback is a second data line on
  the SAI's other sub-block, which costs one more header pin.
- The MCLK ratios the PCM3168A accepts at 44.1 to 96 kHz with 22.5792 and 24.576 MHz [Verify].

## 5. Supporting parts (main board)

| Function | Recommended | Runner-up | Deciding facts (seen 2026-11-18, snapshot) |
|---|---|---|---|
| Op-amps (input receivers, filters, output drivers) | OPA1678IDR, dual CMOS audio op-amp, SOIC-8 | NE5532 (bipolar) [Verify JLC class]; OPA1612 where stage 2's noise budget needs it | OPA1678IDR: LCSC C192421, $0.20 at 5+, 1690 to 7970 in stock; 4.5 nV/rtHz [Verify], runs on split rails up to +/-18 V [Verify] |
| ADC driver (differential into the PCM3168A) | A dual op-amp per channel as a differential attenuator and filter (OPA1678) | OPA1632 fully differential amplifier [Verify price, stock] | Stage 2 decides the topology; listed so the owner's exercise has the part |
| Balanced output driver | Op-amp per leg from the PCM3168A's differential outputs, with build-out resistors | DRV134 (impedance-balanced driver, SOIC-16 wide, LCSC C2651261, price not found) [Verify] | The PCM3168A's outputs are differential already, so a dedicated driver adds little |
| Mute relays (monitor outputs) | Omron G6K-2F-Y, 5 V coil, DPDT, SMD | Panasonic TQ2SA-5V | G6K-2F-Y-TR-5VDC: LCSC C31894287, $1.05 at 1, 277 in stock; another variant C47190, 52 086 to 133 314 in stock but one page says not for new designs [Verify]. TQ2SA-5V: LCSC C2858038, no price seen; RS £2.11 |
| Headphone amplifier | OPA1622 (VSON-10, 3 x 3 mm, has an enable pin usable for a pop-free mute [Verify]) | TPA6120A2DWPR (SOIC-20 PowerPAD) | OPA1622IDRCR: LCSC C2876559, $2.12 to $4.47 at 1 (snapshots disagree). TPA6120A2DWPR: LCSC C70439, $1.94 at 1, 1281 in stock. Final pick waits for the owner's headphone loads |
| 5 V for the Nucleo and logic | TPS563201DDCR buck, 4.5 to 17 V in, 3 A | AP63205 fixed 5 V buck [Verify] | TPS563201DDCR: LCSC C116592, about 69 750 in stock, JLC lists it as Extended |
| Split analogue rails (+/-15 V raw) | An isolated 2 W dual-output module, 12 V in, +/-15 V out (for example A1215S-2WR3, LCSC C48888070, +/-15 V at 66 mA, 10.8 to 13.2 V in), then an LC filter and LDOs | Non-isolated: an inverting buck-boost to -15 V and the +12 V input direct into the positive LDO | Module: no layout work in the switching loop, but 66 mA per rail may be short once the headphone amplifier is counted, and its input range needs a 12 V adapter within 10 % [Verify]. Stage 2's current budget decides; the 3 W or 6 W siblings are the step up |
| Analogue LDOs (+/-12 V) | TPS7A4901 (positive, 36 V, 150 mA, low noise) and TPS7A3001 (negative) | LT3094 / LT3045 or ADP7182 / ADP7118 [Verify price] | TPS7A4901DGNT: LCSC C61422, $0.84 at 1 (another snapshot $1.97), 434 in stock. TPS7A3001 commercial grade: no LCSC price seen, only the military-grade C2867754 at $11 [Verify] |
| Converter 5 V analogue LDO | TPS7A4901 set to 5 V if the PCM3168A's analogue current is under about 120 mA; otherwise a 1 A part such as TPS7A4701 [Verify] | ADP7118 (200 mA) [Verify] | Sized once the current is read from the datasheet (SPEC V23 proposed) |
| Converter 3.3 V digital | A small low-noise LDO from the 5 V rail (for example TLV757P or similar) [Verify part, stock] | The Nucleo's own 3.3 V | Its own LDO keeps the Nucleo's digital noise off the converter's supply |
| Oscillators | YXC 3225 3.3 V CMOS oscillators, one at 24.576 MHz (for example O9322524576MEDA4SI, LCSC C496682, $0.44 at 1) and the 22.5792 MHz sibling [Verify part number, OE pin, phase jitter] | Kyocera KC3225A series (C1987765 for 24.576 MHz) [Verify jitter, price] | Jitter limit: a full-scale 20 kHz sine reaches 105 dB SNR only with clock jitter under about 45 ps rms (from SNR = -20 log10(2 pi f t)), my estimate, not a datasheet figure. Avoid MEMS oscillators (for example SiT8008) unless their jitter figure is under that |
| Clock select and buffer | Both oscillators with output enable, only one enabled; a 74LVC1G157 2:1 multiplexer, then a 74LVC2G34 dual buffer driving the converter's MCLK and the MCU's I2S_CKIN, 33 ohm series resistor at each source | Wired outputs of two tri-state oscillators (no multiplexer) | Generic logic, cheap and stocked [Verify]. Turning the unused oscillator off keeps its tone out of the analogue section |
| Optical S/PDIF (batch 10, stretch) | Everlight PLT133/T10W transmitter (16 Mb/s); a current receiver of the same footprint [Verify: the PLR135 receiver is marked obsolete at Digi-Key] | Toshiba TORX1350 / TOTX1350 | S/PDIF at 96 kHz is about 12.3 Mbaud after biphase coding (2 x 32 bits x 2 channels x 96 kHz), so a 16 Mb/s module covers it and 192 kHz (about 24.6 Mbaud) does not; my arithmetic. PLT133/T10W: LCSC C2940206, $0.37, 0 in stock. TORX1350: LCSC C17194662, $17.80 at 1, out of stock |
| Line and output jacks | Neutrik NMJ6HCD2, 6.35 mm stereo, switched, metal threaded nose, PCB mount | Rean NYS216 (Neutrik's budget brand, right-angle, through-hole) | NMJ6HCD2: LCSC C368502, $2.56 at 1, $1.57 at 100. NYS216: Rapid £1.76, back order. Fixed by its nut, as the plan requires [Verify the panel thickness range] |
| DC input | A panel-mount threaded 2.1 mm DC jack [Verify part] | A PCB-mount DC jack with a locking plug family [Verify] | "A DC jack that grips" (`shield_outline.md` section 10) |
| Power entry protection | P-channel MOSFET reverse-polarity switch, SMBJ15A TVS, resettable fuse [Verify parts] | Series Schottky diode | Commodity; sized in stage 2 with the current budget |

## 6. Panel parts (control panel board, rear connectors)

| Function | Recommended | Runner-up | Deciding facts |
|---|---|---|---|
| Potentiometers, 10 k linear, with and without centre detent | Alps RK09L series, 9 mm, metal shaft: one series offers both (for example RK09L112003S with centre detent, RK09L1140A5L without) [Verify threaded bushing and nut, shaft length options] | Alpha 9 mm (RD901F centre-detent variant, per a retailer claim) [Verify] | The plan asks for one family for matched shaft height. Alps RK09K (snap-in, insulated shaft) also has both detent codes (C0, C1) but has no bushing, so it would not be fixed by a nut |
| Buttons | Omron B3F-5000 series, 12 x 12 mm, through-hole: 10 million operations per Omron | Omron B3F-4000 (12 mm, standard life) [Verify life] | Long-life rating from Omron's own FAQ. A cap through the panel; stem height chosen in stage 2 from the panel stack |
| LEDs | 3 mm diffused through-hole LEDs, fitted by hand at the height that reaches the panel | 0603 SMD LEDs with light pipes [Verify a light pipe family] | Through-hole is cheap, robust and the height is free; light pipes need exact stack heights |
| Headphone jack | Neutrik NMJ6HCD2, as the line jacks | Rean NYS216 | One jack type throughout keeps one footprint and one nut size |
| Footswitch jack (rear) | The same jack | | Mono or TRS pedal both fit a stereo jack |
| USB-C receptacle | A 16-pin USB 2.0 receptacle with through-hole shell stakes, for example GCT USB4105-GF-A [Verify LCSC stock] | HRO TYPE-C-31-M-12 (LCSC C165948) | The plan asks for through-hole shell legs; JLC lists C165948 as surface mount and Extended, so it is only the fallback |
| USB ESD | USBLC6-2SC6 [Verify JLC class] | TPD2E2U06 [Verify] | Standard part for a full-speed pair |
| Ribbon between the boards | 2.54 mm shrouded box header and IDC ribbon, provisionally 2 x 20 | 1.27 mm pitch 2 x 20 header and fine ribbon | Count: 7 pots, 5 buttons, 7 LEDs, OLED I2C (2), two encoders (6), the headphone pair if the amplifier stays on the main board, clean pot reference, supplies, interleaved grounds: about 36 to 40 pins. Fewer if stage 2 picks a multiplexer for the pots (SPEC V12) |

## 7. What the owner decides before stage 2

1. **Converter:** PCM3168A (recommended) or AK4619VN.
2. **Outputs 3 and 4 as balanced line outputs too?** With the PCM3168A the converter channels are
   free; the cost is two jacks and two driver stages (`shield_outline.md` section 8, question 5).
3. **Jacks:** 6.35 mm TRS throughout (as drawn), or XLR or combo connectors on the monitor outputs
   or the inputs.
4. **Headphones:** which models, so the headphone amplifier is chosen for their impedance and
   sensitivity (OPA1622 or TPA6120A2).
5. **S/PDIF on rev A:** footprints and parts fitted by hand when batch 10 starts, or no footprints.
6. **Front panel thickness** (the owner cuts the case): it sets the potentiometers' bushing and
   shaft length, the jack nose length, and the button and LED heights.
7. **Live prices and stock:** the owner checks the recommended parts on LCSC and JLC, or allows
   direct queries to their part pages.

The input stage noise and level exercise (PLAN_BATCHES section 7) is done after decision 1 and
before stage 2 is read.

## 8. Assumptions to verify (proposed additions to SPEC section 9)

| # | Assumption | When |
|---|---|---|
| V20 | The PCM3168A runs TDM at 96 kHz with 8 DAC slots and 6 ADC slots on one line each (BCLK 24.576 MHz), with MCLK at 22.5792 or 24.576 MHz for all four rates, and the H755's SAI keeps up | Batch 5, stage 3 (datasheet), batch 7 (board) |
| V21 | Live LCSC and JLC stock, price and part class for every chosen part | Batch 5, stage 1 sign-off, and again at stage 5 |
| V22 | The chosen oscillators have an output enable and phase jitter under about 45 ps rms | Batch 5, stage 3 |
| V23 | The PCM3168A's analogue supply current, to size its 5 V analogue LDO | Batch 5, stage 2 |
| V24 | The Alps RK09L series offers a threaded bushing, a centre detent and a plain version, and a shaft length for the owner's panel | Batch 5, stage 2 |
| V25 | A current (not obsolete) 16 Mb/s optical receiver exists in the PLR135 footprint | Batch 5, stage 3, if S/PDIF footprints stay |
| V26 | A USB-C receptacle with through-hole shell stakes is stocked at LCSC or JLC | Batch 5, stage 2 |

## 9. Sources

Converters:
- [TI PCM3168A product page](https://ti.com/product/PCM3168A) and datasheet SBAS452A:
  [specifications](https://www.ti.com/document-viewer/PCM3168A/datasheet/specifications),
  [detailed description](https://www.ti.com/document-viewer/PCM3168A/datasheet/detailed_description)
- [LCSC PCM3168APAPR, C529289](https://www.lcsc.com/product-image/C529289.html);
  [JLC PCM3168APAP, C1521535](https://jlcpcb.com/jp/partdetail/TexasInstruments-PCM3168APAP/C1521535)
- [AKM AK4619VN product page](https://www.akm.com/us/en/products/audio/audio-codec/ak4619vn/),
  [AK4619VN datasheet (Mouser)](https://www.mouser.com/datasheet/2/1431/ak4619vn_en_datasheet-3010069.pdf),
  [product brief](https://mouser.com/datasheet/2/1431/Asahi_ak4619vn_Product_Brief-3476019.pdf),
  [evaluation manual](https://www.akm.com/content/dam/documents/products/audio/audio-codec/ak4619vn/akd4619vn-en-evaluationmanual.pdf),
  [spec summary (full-scale input)](https://manualzz.com/doc/59451014/akm-ak4619vn-spec-sheet)
- [LCSC AK4619VN, C3034747](https://www.lcsc.com/product-detail/C3034747.html);
  [Digi-Key AK4619VN](https://www.digikey.fr/en/products/detail/asahi-kasei-microdevices-akm/AK4619VN/14324507);
  [Lisleapex comparison](https://www.lisleapex.com/product/compare-a/ak4619vn_ak4619vn-l_ak4611vq);
  [Digi-Key 2024 automotive guide](https://www.digikey.com/Site/Global/Layouts/DownloadPdf.ashx?pdfUrl=F9499EAD1407463E9AF68E2C470206B4)
- [Cirrus CS42448 product page](https://master-nq.webp2.cirrus.com/products/cs42448);
  [LCSC CS42448-DQZ, C1521507](https://www.lcsc.com/product-detail/audio-interface-ics_cirrus-logic-cs42448-dqz_C1521507.html);
  [LCSC CS42448-CQZR, C2151089](https://lcsc.com/product-detail/Audio-Interface-ICs_Cirrus-Logic-CS42448-CQZR_C2151089.html)
- [ADI AD1938](https://analog.com/en/products/ad1938.html);
  [AD1939 datasheet](https://www-cce.cldnet.analog.com/media/en/technical-documentation/data-sheets/AD1939.pdf);
  [AD1939 distributor price](https://www.omo-ic.com/chip/detail/AD1939WBSTZ.html)
- [PCM186x datasheet (mirror)](https://cdn.hackaday.io/files/6061259313824/pcm1863.pdf);
  [LCSC PCM1863DBTR, C529569](https://www.lcsc.com/product-detail/C529569.html);
  [JLC PCM1863DBTR](https://jlcpcb.com/partdetail/TEXASINSTRUMENTS-PCM1863DBTR/C529569);
  [PCM512x data formats](https://www.ti.com/document-viewer/PCM5121/datasheet/pcm-audio-data-formats-slau3459129);
  [LCSC PCM5122PWR, C962071](https://www.lcsc.com/product-detail/C962071.html);
  [LCSC PCM5122PW, C1540085](https://www.lcsc.com/product-detail/C1540085.html)

Supporting and panel parts:
- [LCSC OPA1678IDR, C192421](https://www.lcsc.com/product-detail/C192421.html);
  [LCSC DRV134UA datasheet, C2651261](https://lcsc.com/datasheet/lcsc_datasheet_2303011730_Texas-Instruments-DRV134UA-1K_C2651261.pdf)
- [LCSC G6K-2F-Y-TR-5VDC, C31894287](https://www.lcsc.com/product-image/C31894287.html?whichImg=0);
  [LCSC G6K-2F-Y-TR DC5, C47190](https://www.lcsc.com/product-image/C47190.html);
  [LCSC TQ2SA-5V, C2858038](https://www.lcsc.com/product-detail/C2858038.html);
  [RS TQ2SA-5V](https://uk.rs-online.com/web/p/signal-relays/2172905)
- [LCSC OPA1622IDRCR, C2876559](https://www.lcsc.com/product-detail/C2876559.html);
  [LCSC TPA6120A2DWPR, C70439](https://www.lcsc.com/product-detail/C70439.html)
- [JLC TPS563201DDCR, C116592](https://jlcpcb.com/partdetail/TexasInstruments-TPS563201DDCR/C116592)
- [LCSC RLT A1215S-2WR3, C48888070](https://www.lcsc.com/product-detail/C48888070.html);
  [Mornsun B1215S-2WR3 datasheet](https://www.lcsc.com/datasheet/lcsc_datasheet_2106070306_MORNSUN-Guangzhou-S--T-B1215S-2WR3_C2684894.pdf)
- [LCSC TPS7A4901DGNT, C61422](https://www.lcsc.com/product-detail/C61422.html);
  [LCSC TPS7A3001MDGNTEP, C2867754](https://www.lcsc.com/product-image/C2867754.html)
- [YXC 24.576 MHz oscillator, C496682](https://lcsc.com/datasheet/lcsc_datasheet_2408141011_YXC-Crystal-Oscillators-O9322524576MEDA4SI_C496682.pdf);
  [Kyocera KC3225A 24.576 MHz, C1987765](https://datasheet.lcsc.com/lcsc/2201301230_Kyocera-KC3225A24-5760C3GE00_C1987765.pdf);
  [SiTime SiT8008 24.576 MHz, C826990](https://www.lcsc.com/product-detail/C826990.html)
- [Everlight PLR135 datasheet](https://akizukidenshi.com/goodsaffix/plr135-t.pdf);
  [Digi-Key PLR135/T (obsolete)](https://www.digikey.com.au/en/products/detail/PLR135%2FT/1080-1431-ND/2693959);
  [Digi-Key PLT133/T10W](https://azcus.digikey.com/en/products/detail/everlight-electronics-co-ltd/PLT133-T10W/2693977);
  [LCSC PLT133/T10W, C2940206](https://fat.lcsc.com/product-image/C2940206.html);
  [LCSC TORX1350A, C17194662](https://www.lcsc.com/product-image/C17194662.html)
- [LCSC Neutrik NMJ6HCD2, C368502](https://www.lcsc.com/product-detail/C368502.html);
  [Rapid: Rean range](https://rapidonline.com/brands/rean-a-brand-of-neutrik-ag)
- [Alps RK09K catalogue](https://www.mikrocontroller.net/attachment/74244/B400_ALPS-RK09K.pdf);
  [Alps RK09L catalogue (Arrow)](https://static6.arrow.com/aropdfconversion/bc270b4eb1c7f0caab93d16a378afa6fba6c5767/productcatalogrv01rk09lenb8437bd47d.pdf);
  [9 mm pots, centre detent (retailer)](https://www.stompboxparts.com/9mm-pots)
- [Omron FAQ: high-durability tactile switch](https://components.omron.com/eu-en/faq/switches/FAQE20078)
- [JLC TYPE-C-31-M-12, C165948](https://jlcpcb.com/partdetail/C165948)
