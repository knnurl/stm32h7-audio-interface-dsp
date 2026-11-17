# Plan

The batches, their status and their order. The detailed specification of each batch is
`docs/PLAN_BATCHES.md`; the reasons are in `docs/PLAN_ASSESSMENT.md`.

One batch is one session. It ends with the build clean, the tests passing, its numbers in
`docs/PROGRESS.md`, its review pack written, and a stop for the owner.

| Batch | Content | Needs hardware | Depends on | Status |
|---|---|---|---|---|
| 0 | Project documents | No | Nothing | Done 2026-11-17 |
| 1 | Foundation: host library, test harness, firmware skeleton | Nucleo | 0 | Built 2026-11-17; target run open |
| 2 | Audio pass-through on breakouts | Nucleo, two breakouts, scope | 1 | Waiting for the modules |
| 3 | Filters, float and Q31 | Nucleo | 1 | Not started |
| 4 | USB audio, full speed. **Portfolio checkpoint P1** | Nucleo, breakouts | 2, 3 | Not started |
| 5 | Shield rev A design, five stages | No | 0 | Outline drafted (`docs/notes/shield_outline.md`) |
| 6 | Dynamics and saturation | Nucleo | 3 | Not started |
| 7 | Shield bring-up and lab session | Shield, lab analyser | 5, 4 | Not started |
| 8 | Strips, monitor mixer, reverb, metering, host control | Shield | 6, 7 | Not started |
| 9 | Room correction | Shield, lab microphone | 8 | Not started |
| 10 | S/PDIF and ASRC (stretch) | Shield | 8 | Not started |
| 11 | Dual-core split and front panel (stretch) | Shield | 8 | Not started |
| 12 | Rev B integrated board (stretch) | New board | 7, 8 | Not started |
| 13 | Portfolio write-up | No | 9 | Not started |

## Core and stretch

Core path: batches 0 to 9, then 13. Stretch, each droppable on its own: 10, 11, 12.

Batch 3 needs no audio hardware, so it can run before batch 2 if the modules are late. Batch 5
runs alongside the firmware batches.

## Portfolio checkpoint P1 (after batch 4)

The Nucleo and two breakouts work as a USB sound card with a parametric EQ. The README shows the
measured latency, CPU and noise tables with their commands. This is the first state worth
showing, and the point at which the owner decides whether to make the repository public.

## What the owner buys or books

| For batch | Item |
|---|---|
| 2 | PCM1808 ADC module, PCM5102A DAC module, jumper wires, jack breakouts, a loopback cable (ordered 2026-11-16) |
| 5 | Nothing until stage 5; then the shield order and the hand-fitted parts |
| 7 | A 12 V supply; a session with the university audio analyser |
| 9 | A session with the university measurement microphone |
