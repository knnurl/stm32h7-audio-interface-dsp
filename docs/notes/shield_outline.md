# Shield rev A: draft outline

Written 2026-11-17, before batch 5 stage 1. It is an outline to react to, not a design: no part
has been checked against live stock, a datasheet or the Nucleo's pin tables today. Part names are
candidates from memory. Batch 5 replaces this file's guesses stage by stage.

## 1. What the board is

A 4-layer board that plugs onto the Nucleo-H755ZI-Q and carries everything analogue. USB, the
MCU and the debugger stay on the Nucleo. SMT parts on the top side only (JLC Economic assembly);
jacks and other through-hole parts fitted by hand.

```
12 V DC in -> protection -> +5 V buck ----------> Nucleo supply, digital 3.3 V LDO
                         -> split-rail converter -> LDOs -> +/-9 to 12 V analogue
                         -> quiet 5 V / 3.3 V LDO -> converter analogue supply and reference

22.5792 MHz osc --+
24.576 MHz osc ---+-> select -> buffer -> converter MCLK, MCU I2S_CKIN

LINE IN L/R (TRS) -> protection -> balanced receiver / attenuator -> anti-alias -> ADC
DAC 1-2 -> reconstruction filter -> balanced driver -> mute relay -> MONITOR OUT L/R (TRS)
DAC 3-4 -> reconstruction filter -> headphone amplifier -> mute -> PHONES (TRS)
                 converter <-> TDM bus, I2C control <-> Nucleo headers
Toslink RX -> MCU SPDIFRX        MCU SAI (S/PDIF mode) -> Toslink TX
Header: OLED (I2C), two encoders, two spare GPIO
```

## 2. Blocks

| Block | Function | Candidate approach | Main question for batch 5 |
|---|---|---|---|
| Power entry | 12 V barrel jack, reverse-polarity and over-voltage protection, fuse | P-FET or ideal-diode, TVS, polyfuse | Current budget; what the Nucleo draws |
| Digital supply | 5 V for the Nucleo, 3.3 V for the shield's logic | Small buck to 5 V, LDO to 3.3 V | How the Nucleo is fed: which pin, which jumper [Verify in the board manual] |
| Analogue rails | Bipolar rails for the op-amps | An isolated +/-12 or +/-15 V DC-DC module, or an inverting converter, then LDOs or capacitance multipliers | Noise at the switching frequency against the converter's floor |
| Converter supply | Quiet analogue supply and reference | One low-noise LDO, used only here | Which rails the chosen converter needs |
| Clocks | Two oscillators, one enabled at a time | Oscillators with an enable pin, outputs joined through a buffer, series termination at each load | Jitter figure worth paying for; trace length to the MCU pin |
| Converter | 2 ADC and 4 DAC channels on one TDM bus, 44.1 to 96 kHz, slave to the oscillator | AK4619VN (4 in, 4 out); CS42448; PCM3168A; or a separate ADC and DACs | The trade study: performance, stock, price, package, JLC class |
| Line inputs | Balanced in at +4 dBu nominal, +20 dBu at 0 dBFS | Passive attenuation into a differential receiver per channel, feeding the ADC differentially | Common-mode rejection with 1 % against 0.1 % resistors; input impedance |
| Monitor outputs | Balanced out, +18 dBu at 0 dBFS | Filter and gain per DAC leg, impedance-balanced or cross-coupled driver | Whether a simple two-op-amp driver is enough |
| Headphone output | Stereo, 32 to 300 ohm loads | A dedicated headphone amplifier or a buffered op-amp | Output power target; DC at the jack |
| Muting | No thumps at power-up, power-down or rate changes | Relays on the monitor outputs, mute transistors or the amplifier's enable on phones; a supervisor holds mute until rails and clocks are good | Sequencing, and what happens when 12 V is pulled |
| S/PDIF | Optical in and out | Toslink receiver and transmitter modules | Which MCU pins; 96 kHz support of the modules |
| Control panel | Knobs, buttons, LEDs, display (section 9) | A ribbon header to a separate panel board | ADC pins or a multiplexer |
| Protection | ESD and over-voltage at every jack | Series resistance and clamp diodes to the rails; DC blocking where needed | Clamp leakage against distortion |
| Test access | Bring-up without probing fine pitch | Test points on every rail, clock and TDM line; jumpers to isolate each rail; a ground post | The bring-up order for batch 7 |

## 3. Levels

- +18 dBu is 6.16 V RMS, 8.7 V peak, differential. Each leg swings 4.35 V peak, so analogue rails
  of +/-9 V or more leave margin with ordinary op-amps.
- +20 dBu at the input is 7.75 V RMS differential. The input stage attenuates it to the
  converter's full-scale input, so the rails do not limit it; the attenuator's resistor noise
  and the receiver's noise set the floor.
- The dBu value of 0 dBFS is a choice: higher means more headroom from hot sources and a higher
  noise floor relative to nominal level. Stage 2 proposes the value with its cost.

## 4. Grounding and layout intent

- One unbroken ground plane on layer 2. No split. Separation is by placement: power entry and
  switching converter in one corner, digital and clocks near the Nucleo headers, the converter
  at the boundary, analogue stages and jacks on the far edge.
- Stack: signal, ground, power, signal.
- The 12 V return, the jack sleeves and the Nucleo's ground meet the plane; the USB cable's
  shield stays on the Nucleo. A ground loop through the PC and the monitors' mains earth is
  possible with any USB interface; stage 2 says what the design does about it (balanced outputs
  are the main defence).
- The clock runs short and direct from the buffer to the converter and to the MCU pin, away from
  the analogue inputs.
- The owner routes the analogue and clock nets. Claude writes the placement plan and routing
  rules first and reviews the board against them.

## 5. Connection to the Nucleo

Signals the shield needs. Pin names are from memory of the STM32H7 pin map [Verify every row
against the Nucleo manual's tables in batch 2 and batch 5].

| Signal | Count | Candidate pins |
|---|---|---|
| TDM: bit clock, frame sync, data out, data in | 4 | SAI1: PE5, PE4, PE6, PE3 |
| Audio master clock into the MCU | 1 | I2S_CKIN: PC9 |
| Converter control | 2 | I2C1: PB8, PB9 |
| S/PDIF in | 1 | An SPDIFRX input not taken by Ethernet or the serial port |
| S/PDIF out | 1 | A second SAI sub-block's data pin |
| Oscillator select, converter reset, mute, rail-good | 4 | Any GPIO |
| OLED (shares the I2C bus) and encoders | 4 to 6 | Any GPIO with timer encoder inputs if convenient |
| Supply to the Nucleo and ground | | The board manual's external supply pin |

Two ways to mount, decided in stage 2:

- **Zio sockets** (fitted on the board as shipped): the shield carries male pins and nothing is
  soldered to the Nucleo. Only works if every signal above is on a Zio pin.
- **Morpho rows** (bare holes on the board as shipped): male headers are soldered into the Nucleo
  first. Every MCU pin is available.

## 6. Size and cost

- The Nucleo-144 is about 70 by 133 mm [Verify]. The shield must span the chosen headers and
  hold a barrel jack, five 6.35 mm TRS jacks (two in, two monitor out, phones) and two Toslink
  modules along its free edges.
- JLC's 4-layer price steps up above 100 by 100 mm [Verify on a live quote]. Stage 2 says
  whether the board fits inside that and what it costs if it does not.
- Rough cost aim for two assembled boards: 80 to 150 pounds [Verify at stage 5].

## 7. Bring-up order (for batch 7)

1. Rails, unloaded, with the rail jumpers open and the Nucleo absent.
2. Rails, loaded, section by section.
3. Oscillators and the clock at the converter and at the MCU pin.
4. Converter control over I2C.
5. Digital loopback through the converter's serial port.
6. Analogue: outputs muted, then a -20 dBFS tone into a dummy load, then inputs.

## 8. Open questions for the owner

1. Mounting: Zio sockets (no soldering on the Nucleo) if the pins allow it, or morpho?
2. Jacks: 6.35 mm TRS throughout, or XLR on the monitor outputs?
3. Headphone loads to support: which headphones will you use?
4. S/PDIF on rev A at all, or leave the footprints unpopulated until batch 10?
5. Should outputs 3-4 also appear on balanced line jacks, so an active crossover mode stays
   possible later? It costs two jacks and a driver stage.

## 9. Control panel board (added 2026-11-17)

The owner chose the full control set. It does not fit on the shield beside the jacks, so it is a
second small board, joined to the shield by a ribbon cable, and reused in rev B.

| Item | Count | Notes |
|---|---|---|
| Potentiometers, 10 k linear | 7 | Bass, mid, treble (centre detent); monitor volume; headphone volume; effect amount; blend. Each wiper has an RC filter and goes to an ADC input. |
| Buttons | 5 | Effect select, effect on and off, mute, dim, tap tempo |
| LEDs | 7 | Signal and clip per input; mute; dim; effect on |
| OLED and two encoders | header | Fitted in batch 11 |

Questions for stage 2: seven ADC inputs straight to the Nucleo, or one input and an analogue
multiplexer on the panel; a clean reference for the potentiometers; ribbon length and what it
picks up; panel size (seven potentiometers at about 18 mm pitch is about 130 mm wide).

## 10. Enclosure and product layout (added 2026-11-17)

The owner wants rev A in an enclosure, built as if it were a product: professional looking,
intuitive, reliable. The sketch is `docs/notes/device_look.svg`. This section replaces the
floor plan in `shield_outline.svg` and the 100 by 100 mm size in section 6. Everything here is a
proposal for batch 5 to check; no dimension has been checked against a real case or part.

**Layout**

- A desktop box of about 170 by 55 by 140 mm. Proposed: an extruded aluminium case with board
  slots (Hammond 1455 family or similar [Verify sizes and price]), with the front and rear
  panels made as circuit boards: black solder mask, printed legends, drilled and routed by the
  board house.
- Main board: 160 by 100 mm, the Eurocard size such cases take in their slots [Verify]. Every
  rear connector sits on its rear edge: power switch, 12 V jack, USB-C, optical in
  and out, two line inputs, two monitor outputs.
- The Nucleo plugs into the underside of the main board on rev A [Verify the stack height
  against the case]. Rev B is the same board outline with the MCU on it, so the case, both
  panels and the control board carry over.
- Control panel board: behind the front panel, joined to the main board by a ribbon inside the
  case. The headphone jack moves to the front, next to its volume. (No footswitch: owner,
  2026-11-18.)
- Front panel groups, left to right, in signal order: input (signal and clip LEDs, blend),
  display (OLED, two encoders), effect (select, on, tap, amount), tone (bass, mid, treble),
  output (headphone jack and volume, mute, dim, and the largest knob: monitor volume).

**USB connector**

- USB-C on the rear panel (proposed; USB-B is the alternative: larger and very robust, but
  dated). It is a data-only device port: two 5.1 k resistors on the CC pins, ESD protection,
  through-hole shell anchors, VBUS used only to detect the host.
- On rev A the data pair runs from the socket through the header pins to the MCU, in place of
  the Nucleo's own user USB socket [Verify which Nucleo solder bridges and its USB power switch
  are involved]. Full speed tolerates this. Fallback: a short internal panel-mount lead from the
  Nucleo's socket.
- The ST-LINK port stays inside the case. Firmware updates in normal use go over the main USB
  port through the MCU's built-in bootloader [Verify], so the case is opened only for debugging.

**Reliability measures to design in**

- Jacks and potentiometers fixed to the panels by their nuts, so plugging and turning put no
  force on solder joints.
- A power switch, reverse-polarity and over-voltage protection, and a DC jack that grips.
- Output mute relays held open until rails and clocks are good, and opened first at power-down.
- ESD protection on every external connector; the case bonded to ground at one defined point.
- Watchdog and brown-out reset; settings stored with a checksum and a fallback to defaults.

**What it costs**

- The main board passes 100 by 100 mm, where JLC's 4-layer price steps up [Verify on a quote].
- Three more boards (control panel, front panel, rear panel) and the case.
- Mechanical work: panel drawings that match the connector and knob positions exactly. One
  KiCad project holds all the boards so the positions stay tied together.

**Not covered:** selling a product needs EMC and safety compliance work (UKCA or CE marking).
That is outside this project; the design choices above only avoid making it harder later.

## 11. Confirmed by the owner, 2026-11-17

- USB-C. The front-panel order as drawn. Monitor volume is the large knob.
- The owner makes the aluminium case himself by CNC or waterjet. This replaces the bought
  extrusion and the circuit-board panels proposed in section 10. The case is designed around the
  boards: the 160 by 100 mm main board stays as the working size but is free to change.
- What batch 5 now delivers for the case: a parametric model (CadQuery, as for the Psyight node
  box) that takes connector and control positions from the KiCad boards, and exports a STEP
  model plus flat DXF profiles for the panels.
- Open questions for the owner at that stage: sheet thickness and whether the body is folded
  sheet, milled, or flat plates with standoffs; how legends are applied (engraving, laser
  marking on anodised aluminium, or a printed overlay); the finish.

