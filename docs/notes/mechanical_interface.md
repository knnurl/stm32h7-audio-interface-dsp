# Mechanical interface (batch 5, stage 2): draft

2026-11-18. The table the enclosure work starts from. Regenerated from the KiCad files by a script
once they exist (stage 3/4). **Draft:** many heights are estimates marked [Verify]; the owner can
measure the Nucleo's with calipers.

Coordinates: origin at the main board's front-left corner seen from above with the rear at the
top; x to the right, y to the rear, z up from the case's outer bottom face. Note: seen from
behind, the rear panel is mirrored relative to `device_look.svg`'s top view.

## 1. Boards

| Board | Size | Layers | Mounting |
|---|---|---|---|
| Main | **200 x 100 mm (proposed; 160 does not fit the rear connectors)** | 4 | 4 x M3 at (4, 4), (196, 4), (4, 96), (196, 96) on standoffs from the floor, insulated except the chassis-bond hole near the USB-C (about x = 48, y = 95) |
| Nucleo-H755ZI-Q | 133.34 x 70 mm [Verify UM2408 Figure 5] | | under the main board, long side along x, ST-LINK end at the left wall, on **insulating** standoffs |
| Panel | 160 x 46 mm, vertical behind the front panel | 2 | held by the pot, encoder and jack nuts; 2 optional holes, not bonded |

## 2. Stack height (SPEC V14)

| Item | z bottom to top (mm) | Source |
|---|---|---|
| Case floor, 2 mm aluminium (assumed) | 0 to 2 | owner's case |
| Standoffs under the Nucleo, clearing its bottom-side Zio male pins (about 6 mm [Verify]) | 2 to 10 | estimate |
| Nucleo PCB | 10 to 11.6 | 1.6 mm [Verify] |
| Tallest Nucleo top part: RJ45 CN14, about 13.5 mm [Verify] | to 25.1 | estimate |
| Board-to-board spacing 15 mm (tall morpho sockets) | 11.6 to 26.6 | |
| Main board PCB | 26.6 to 28.2 | |
| Tallest main board part: NMJ6HCD2 body 15.67 mm (LCSC attribute); module 12 mm; 470 uF caps about 12.5 mm | to 43.9 | |
| Lid inner face (55 mm case, 2 mm lid) | 53 | |
| **Clearance** | **9.1 mm** | fits on paper |

Option: a cut-out in the main board over the RJ45 lets the spacing drop to about 11 mm (standard
2.54 mm male plus 8.5 mm female), lowering everything by 4 mm and the rear jacks' axis towards the
panel's centre. Rear jack axis height above the board about 8 mm [Verify], so z about 36 (34 % of
55 from the top).

Inside height about 51 mm, so the panel board is 46 mm, not 52 mm (z about 4.5 to 50.5).

## 3. Rear connectors (main board rear edge, y = 100), x centres in mm, proposed

| Item | x | Part | Height or axis |
|---|---|---|---|
| Power switch (panel mount, wired) | 8 | [Verify part] | |
| 12 V DC jack (panel mount, wired) | 23 | [Verify part] | |
| USB-C | 37 | USB4105-GF-A | shell about 3.3 mm tall [Verify] |
| Optical in (footprint) | 50 | PLR135 class [Verify] | |
| Optical out (footprint) | 62 | PLT133/T10W | |
| Line in 1, 2 | 80, 100.5 | NMJ6HCD2 (18.2 wide) | axis about 8 [Verify] |
| Monitor out L, R | 121, 141.5 | NMJ6HCD2 | |
| Line out 3, 4 | 162, 182.5 | NMJ6HCD2 | |

Jack pitch 20.5 mm leaves 2.3 mm between bodies; straight plugs fit, large right-angle plugs may
not [owner judges]. NMJ6HCD2: panel up to 4.7 mm, plastic nut (Neutrik page) [Verify the drawing].

## 4. Front controls (positions from `device_look.svg` at its 5 px/mm scale, for a 170 mm panel;
centred on a wider panel)

| Control | x from panel left (mm) | from panel top (mm) | Part |
|---|---|---|---|
| Clip LEDs 1, 2 | 6, 11.6 | 13 | 3 mm TH |
| Signal LEDs 1, 2 | 6, 11.6 | 17.6 | 3 mm TH |
| Blend | 11.4 | 33.6 | RK09L, no detent |
| OLED window | 27.6 to 53.6 | 9 to 22 | batch 11 |
| Encoders select, value | 33.6, 47.6 | 33.6 | EC11 class [Verify] |
| FX select, on, tap buttons | 65, 74, 83 | 14.3 | B3F-5000 [Verify height] |
| FX on LED | 74 | 9.7 | |
| FX amount | 74 | 33.6 | RK09L |
| Bass, mid, treble | 97, 110.6, 124.2 | 33.6 | RK09L with centre detent |
| Phones jack | 139.6 | 14.3 | NJ6FD-V vertical: 12 mm hole, panel 1.2 to 1.5 mm, so a 1.5 mm spot face in the 2 mm panel (Neutrik sheet); height [Verify] |
| Phones volume | 139.6 | 34.5 | RK09L |
| Mute, dim buttons | 153, 163 | 14.3 | B3F-5000 |
| Mute, dim LEDs | 153, 163 | 9.7 | |
| Monitor volume | 158 | 33.6 | RK09L, large knob |

Pots (Alps RK09L series datasheet): M9 x 0.75 bushing, 6 mm metal shaft, shaft length L1 12.5,
15, 20 or 25 mm from the mounting surface, with or without centre detent. With a 2 mm panel,
L1 = 15 mm leaves about 10 mm for a knob after the nut. V24: series confirmed; exact vertical
10 k linear part numbers with and without detent [Verify].

## 5. Depth (y)

Rear panel 2 + main board 100 + gap for the ribbon header about 15 + panel board 1.6 + pot body
about 7.5 [Verify] + front panel 2 = about 128 mm, inside a 140 mm case.

## 6. Still open

- Nucleo outline, hole positions and heights: UM2408 Figure 5 is an image with no text layer, so
  133.34 x 70 mm and every height above stay [Verify]. The owner measures with calipers: the
  RJ45, the Zio sockets, the jumpers, the bottom-side pin length, the hole positions, and whether
  the holes are plated to ground.
- NMJ6HCD2 and NJ6FD-V: Neutrik's technical sheets (read 2026-11-18) give panel thickness, hole
  and materials but no drawing; heights and pin positions come from a sample or the footprint
  download.
- B3F-5000 height and caps, encoder bodies, Toslink module dimensions, DC jack and switch parts.

## 7. From the transcripts

#78: the mid-mount USB-C forced a cut-out and a thinner board; connectors around the perimeter.
Not taken (rear-panel USB-C on a 1.6 mm board). The cut-out idea is kept as the RJ45 option above.
