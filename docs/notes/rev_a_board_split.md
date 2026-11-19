# Rev A in 100 x 100 mm boards (batch 5, stage 2 addendum)

2026-11-19. The owner's decision: several 4-layer boards no larger than 100 x 100 mm (about £10 for
five at JLC, owner's quote), joined by header cables, instead of one 200 x 100 mm main board.
The order stays parked; stage 3 (schematics) goes ahead. This note supersedes
`rev_a_architecture.md` sections 11.1 (ribbon) and 13 (board sizes), and the board outlines in
`mechanical_interface.md` section 1. Everything else in the stage 2 notes stands.

## 1. The boards

| Board | Size, layers | Holds |
|---|---|---|
| **D, power and digital** (left, x 0 to 100) | 100 x 100, 4 | 12 V entry and protection; both TPS563208 bucks (5V_DIG, 5V5_PRE); the WRA1215S-3WR2 module and its LC filters; the RAILS_OK supervisor; the Nucleo's morpho sockets; USB-C with its ESD and VBUS divider; optical in and out (footprints); the BOOT0 recovery header; the panel ribbon header with the pot reference buffer and the wiper, button and encoder filters |
| **A, converter and analogue** (right, x 100 to 200) | 100 x 100, 4 | the linear regulators (+/-12V_ANA, 5V_ANA, 3V3_A); PCM3168A; both oscillators, the mux and the clock buffer; input stages 1 and 2; monitor output stages and relays; line 3/4 output stages and relay; the OPA1622 headphone amplifier; four rear TRS jacks; the chassis strip |
| **PL, panel left** | about 80 x 46, 2 | LEDs 1 to 4 and 7, blend and FX amount pots, both encoders, the OLED header, FX select, on and tap buttons |
| **PR, panel right** | about 80 x 46, 2 | bass, mid, treble, monitor and phones pots; mute and dim buttons and LEDs; the NJ6FD-V phones jack |

Stacking was ruled out: a second layer of boards does not fit the 55 mm case, and the rear
connectors need about 192 mm of edge whatever the boards are.

**Every switching converter is on D; A has only linear regulators.** The module's raw +/-15 V
(after its LC filters), 5V5_PRE and 5V_DIG cross the link; A makes its own clean rails.

**The oscillators sit on A beside the converter.** The PCM3168A's SCKI decides its conversion
quality, so its clock never leaves board A; the MCU receives a buffered copy over the link
(I2S_CKIN, PC9). The MCU is the TDM master; jitter on BCK and LRCK does not reach the converter's
modulators [Verify SBAS452A: SCKI is the only conversion clock].

**3V3_A** for the converter's VDD pins, the oscillators, the mux and the buffer comes from a
TPS7A2033 on 5V5_PRE (the TPS7A2050's family, so one more value of a part already used, and a
quiet rail for the clocks). This replaces the AMS1117 on 5V_DIG. Board D's optical modules and
pull-ups use the Nucleo's 3V3 (UM2408 7.4.7: up to 1300 mA).

## 2. Defaults taken for the schematics (the owner may reverse any)

1. **Line outputs 3 and 4 go to a 2 x 5 header on A, not to jacks.** Four jacks at 20.5 mm pitch
   fill A's rear edge (82 mm plus margins); six do not fit 100 mm. Their output stages and relay
   are drawn and fitted, so a small jack board or a later revision adds the jacks.
2. **Phones jack NJ6FD-V** on PR. Whether the front panel is 1.5 mm (recommended) or 2 mm with a
   spot face does not change the schematic.
3. **The pot reference is buffered** (Claude's stage 2 review point): a rail-to-rail follower on
   the Nucleo's VREF+ drives POT_REF, so seven pots (2.3 mA) and the ribbon no longer load the ADC
   reference. A 0 ohm link bypasses the buffer, fitted open, to go back to the stage 2 wiring.
4. **The panel is two boards**, PL and PR, joined by a short jumper, so both are under 100 mm too.
5. **V29 and V30 open:** the Nucleo's 5 V current and CN12 pins 12 and 14 stay as assumed in stage
   2, marked [Verify] on the sheets.

## 3. Cables between the boards

All IDC ribbon, 2.54 mm, shrouded box headers, conductor n = pin n. Odd pins on one row, even on
the other, so neighbours in the cable are n and n + 1.

### 3.1 J_LINK, D to A (2 x 20, about 60 mm)

| Pin | Signal | Direction | | Pin | Signal | Direction |
|---|---|---|---|---|---|---|
| 1 | GND | | | 21 | HP_EN | D to A |
| 2 | MCLK_MCU (33 ohm at A's buffer) | A to D | | 22 | RAILS_OK | D to A |
| 3 | GND | | | 23 | GND | |
| 4 | BCK (33 ohm at D) | D to A | | 24 | GND | |
| 5 | GND | | | 25 | 5V_DIG (relay coils) | D to A |
| 6 | LRCK (33 ohm at D) | D to A | | 26 | 5V_DIG | D to A |
| 7 | GND | | | 27 | GND | |
| 8 | DIN1 (33 ohm at D) | D to A | | 28 | 5V5_PRE | D to A |
| 9 | GND | | | 29 | 5V5_PRE | D to A |
| 10 | DOUT1 (33 ohm at A) | A to D | | 30 | GND | |
| 11 | GND | | | 31 | GND | |
| 12 | I2C1_SCL | D to A | | 32 | +15V_RAW | D to A |
| 13 | I2C1_SDA | both | | 33 | +15V_RAW | D to A |
| 14 | CODEC_RST_n | D to A | | 34 | GND | |
| 15 | CODEC_OVF | A to D | | 35 | GND | |
| 16 | GND | | | 36 | -15V_RAW | D to A |
| 17 | OSC_SEL | D to A | | 37 | -15V_RAW | D to A |
| 18 | OSC_22M_EN | D to A | | 38 | GND | |
| 19 | MUTE_MON | D to A | | 39 | GND | |
| 20 | MUTE_LINE34 | D to A | | 40 | GND | |

- Every fast line (pins 2 to 10) has a ground on both sides in the cable. Series resistors sit at
  the driving end.
- Supply currents: 5V5_PRE about 0.26 A (5V_ANA 0.21 A plus 3V3_A), each 15 V rail 0.09 A worst,
  5V_DIG three relay coils; two conductors each, and grounds beside each pair. 28 AWG carries
  about 1 A [Verify].
- The control lines keep their pull-downs on A, next to what they switch, so an unplugged cable
  mutes too. RAILS_OK is pulled up on D; A gates the relay drivers and HP_EN with it in hardware.
- The two boards' grounds join only through this cable's 17 ground conductors. The Nucleo meets
  D only.

### 3.2 J_PANEL, D to PL (2 x 20, about 150 mm)

| Pin | Signal | | Pin | Signal |
|---|---|---|---|---|
| 1 | GND | | 21 | LED4 input 2 clip |
| 2 | POT_REF (buffered VREF+) | | 22 | LED5 mute |
| 3 | POT1 bass | | 23 | LED6 dim |
| 4 | POT2 mid | | 24 | LED7 FX on |
| 5 | POT3 treble | | 25 | PANEL_3V3 |
| 6 | POT4 monitor | | 26 | GND |
| 7 | POT5 phones | | 27 | ENC1_A |
| 8 | POT6 FX amount | | 28 | ENC1_B |
| 9 | POT7 blend | | 29 | ENC1_SW |
| 10 | POT_GND | | 30 | ENC2_A |
| 11 | GND | | 31 | ENC2_B |
| 12 | BTN1 FX select | | 32 | ENC2_SW |
| 13 | BTN2 FX on | | 33 | GND |
| 14 | BTN3 tap | | 34 | I2C4_SCL |
| 15 | BTN4 mute | | 35 | I2C4_SDA |
| 16 | BTN5 dim | | 36 | GND |
| 17 | GND | | 37 | PANEL_3V3 |
| 18 | LED1 input 1 signal | | 38 | GND |
| 19 | LED2 input 1 clip | | 39 | not connected |
| 20 | LED3 input 2 signal | | 40 | GND |

The headphone pins of the stage 2 table leave this cable: they now run from A. The rest keeps
the stage 2 rules (11.2 to 11.4): pots between POT_REF and POT_GND, switches to ground with
pull-ups and filters on D, LEDs sunk by the MCU through their resistors on the panel.

### 3.3 J_PJ, PL to PR (2 x 8, about 30 mm)

| Pin | Signal | | Pin | Signal |
|---|---|---|---|---|
| 1 | POT_REF | | 9 | BTN4 mute |
| 2 | POT1 bass | | 10 | BTN5 dim |
| 3 | POT2 mid | | 11 | LED5 mute |
| 4 | POT3 treble | | 12 | LED6 dim |
| 5 | POT4 monitor | | 13 | PANEL_3V3 |
| 6 | POT5 phones | | 14 | GND |
| 7 | POT_GND | | 15 | GND |
| 8 | GND | | 16 | GND |

### 3.4 J_HP, A to PR (2 x 3, about 120 mm)

| Pin | Signal | | Pin | Signal |
|---|---|---|---|---|
| 1 | HP_L | | 4 | HP_R |
| 2 | HP_L_RET | | 5 | not connected |
| 3 | HP_R_RET | | 6 | not connected |

Each signal is next to its own return. The returns connect to the OPA1622's ground on A only and
to the jack's sleeve on PR, never to the panel's ground (stage 2 section 7). Pins 5 and 6 stay
unconnected so the cable adds no second ground path between A and the panel.

## 4. The Nucleo under D

The morpho rows (2 x 35 at 2.54 mm, about 89 mm long) must lie wholly under D. The Nucleo's long
side runs along x with its ST-LINK end towards A: the ST-LINK section sits about 33 mm in under A,
and the RJ45 and user USB end at the left wall [Verify the morpho positions on the owner's board
with calipers, with the heights of V14]. A's ground plane faces the ST-LINK across about 15 mm;
stage 4 checks that A's bottom layer carries no analogue traces over it. The ST-LINK's USB is
inside the case: debug with the lid off, or a short extension to a panel hole.

## 5. Cost

Two 4-layer designs and two 2-layer designs. JLC charges assembly setup and a stencil per design,
and an extended part used on two boards is charged on both [Verify on the quote]. Here nearly
every extended part lives on one board: op-amps, the converter and the linear regulators on A,
the bucks and the module on D.

## 6. From the transcripts

Read for this addendum: #78 again in full (the batch's transcript list: #78, #142).

- **#78:** Phil sections the schematic into pages by function (power, controller, memory, USB,
  peripherals, codec and analogue), puts 33 ohm series resistors on clock lines "at the output of
  the transmitter", one 100 nF per VDD pin plus bulk, filtered 3.3 V and series-R-plus-capacitor
  low-pass filters on the pot connectors' ADC inputs, ESD and an RF filter on each audio input, a
  100 ohm build-out on each output, and labels differential pairs with _P and _N. All taken: the
  link's series resistors sit at each driving end, the pot filters stay on D next to the MCU,
  and the sheets of stage 3 follow his sectioning by function, one board per project.
- **#78** also keeps the analogue section away from digital parts "not only X Y but also on the
  z-axis", with ground planes between. Taken one step further: the analogue section is on its own
  board, with every switcher on the other board.
