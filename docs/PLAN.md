# Plan

The batches, their status and their order. The detailed specification of each batch is
`docs/PLAN_BATCHES.md`; the reasons are in `docs/PLAN_ASSESSMENT.md`.

One batch is one session. It ends with the build clean, the tests passing, its numbers in
`docs/PROGRESS.md`, its review pack written, and a stop for the owner.

| Batch | Content | Needs hardware | Depends on | Status |
|---|---|---|---|---|
| 0 | Project documents | No | Nothing | Done 2026-11-17 |
| 1 | Foundation: host library, test harness, firmware skeleton | Nucleo, for the target run | 0 | Done 2026-11-17, on the board |
| 2 | Audio pass-through on breakouts | Nucleo, two breakouts, scope | 1 | Waiting for the modules |
| 3 | Filters, float and Q31, and the tone control | Host part: none. Target part: Nucleo | 1 | Done 2026-11-17: host part, and on the board (bit-identical, cycles measured) |
| 4 | USB audio, USB MIDI, Ableton. **Portfolio checkpoint P1** | Nucleo, breakouts | 2, 3 | Not started |
| 5 | Rev A boards: main board and control panel, five stages | No | 0 | Outline drafted |
| 6 | Dynamics and saturation | Host part: none. Target part: Nucleo | 3 | Done 2026-11-17: host part, and on the board (cycles measured) |
| 7 | Bring-up of both boards, lab session | Both boards, lab analyser | 4, 5 | Not started |
| 8a | Control core: registry, knob ownership, protocol, MIDI mapping, presets | None (the UART console for the target part) | 1 | Done 2026-11-17 except the supply-cut test of the flash store (SPEC V18) |
| 8b | Effect slot, reverb and tempo | Host part: none. Target part: Nucleo | 3, 6 | Host part and cycles on the board done 2026-11-17; the listening check waits for batch 2 |
| 8c | The full signal path on the boards | Both boards | 6, 7, 8a, 8b | Not started |
| 8d | Control panel firmware | Panel board, or a breadboard | 8a (7 for the real panel) | Not started |
| 9 | Room correction | Both boards, lab microphone | 8c | Not started |
| 10 | S/PDIF and ASRC (stretch) | Both boards | 8c | Not started |
| 11 | Dual-core split, display and encoders (stretch) | Both boards | 8c, 8d | Not started |
| 12 | Rev B main board (stretch) | New board | 7, 8c | Not started |
| 13 | Portfolio write-up | No | 9 | Not started |

## Core and stretch

Core path: batches 0 to 9 (with 8a to 8d), then 13. Stretch, each droppable on its own: 10, 11,
12.

Without any hardware, progress continues on the host parts of 3, 6 and 8b, and on 8a. Batch 5
runs alongside the firmware batches.

## Portfolio checkpoint P1 (after batch 4)

The Nucleo and two breakouts work as a USB sound card with a parametric EQ, the tone control
and a USB MIDI port, and run in Ableton Live. The README shows the
measured latency, CPU and noise tables with their commands. This is the first state worth
showing, and the point at which the owner decides whether to make the repository public.

## What the owner buys or books

| For batch | Item |
|---|---|
| 2 | PCM1808 ADC module, PCM5102A DAC module, jumper wires, jack breakouts, a loopback cable (ordered 2026-11-16) |
| 4 | Ableton Live on the owner's PC (he confirms the version) |
| 5 | Nothing until stage 5; then both boards and the hand-fitted parts (pots, jacks, buttons, USB-C socket, ribbon) |
| 7 | A 12 V supply; a session with the university audio analyser |
| 8d | Only if the panel board is late: three 10 k linear pots, two tactile buttons, two LEDs |
| 9 | A session with the university measurement microphone |
