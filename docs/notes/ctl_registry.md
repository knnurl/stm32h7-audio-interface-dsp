# Design note: the parameter registry and the hand-off to audio

Batch 8a. `ctl_params`, `ctl_param_table.c`, `ctl_queue`, `ctl_core`.

## Purpose

One place that says what the device can be told: every knob, button, PC command, MIDI control
change and preset ends up as a write to a registry entry, and the audio level hears of it through
one queue. The registry is the contract the PC client, the MIDI map, the presets and (batch 8d)
the display are written against.

## Structure

- **One const table**, `ctl/src/ctl_param_table.c`: 169 parameters today, capacity 192
  (`CTL_MAX_PARAMS`, checked at compile time). Each entry: stable numeric id, snake_case name,
  sentence-case label, unit, range, default, curve, smoothing time, flags.
- **Ids by group, with gaps**: 100 input 1, 200 input 2, 300 mixer, 350 reverb, 400 slot, 410 to
  489 effects, 500 tone, 600 speaker, 700 headphones, 800 monitor controls, 900 settings, 910
  knob modes, 1000 meters. A removed parameter keeps its id reserved. Presets store ids, never
  table positions, so the table can be reordered or grown without breaking stored presets.
- **Macros for repetition**: the two input strips and the three four-band PEQs come from one
  macro each, so the strips cannot drift apart. Rejected: generating the table from a Python
  script, which would put the declaration in two places.
- **Curves**: linear; log (frequencies, times, ratios); volume (max + 60 log10 x dB, the cube
  law of a fader, floored at the minimum, which means silence); step (switches and selectors).
- **Flags**: knob, button, preset (in presets and the power-on record), setting (power-on record
  only: listening corrections, knob modes, MIDI channel), read-only (meters). Mute is neither a
  preset nor a setting, so the outputs always start muted (hardware safety rule).
- **The MIDI flag of the plan became derived**: whether a parameter has a CC is read from the
  MIDI map, so it is declared once.
- **Values** are floats in engineering units, clamped on every write; NaN gives the default; step
  parameters round to the nearest integer.

## The hand-off to the audio level

`ctl_queue` carries (index, value) from the main loop to the audio interrupt.

- A latest-value slot and a pending flag per parameter, and a ring of indices. An index enters
  the ring only when its flag was clear, so it is in the ring at most once and the ring
  (capacity 193) **can never overflow**: in a burst the newest value of each parameter wins, by
  construction, and nothing blocks or is dropped. The plan asked for "newest wins on overflow";
  this removes the overflow instead.
- The consumer takes at most `max` entries per call, so its time per block is bounded.
- Ordering: the producer stores the value, fences, reads the flag; the consumer clears the flag,
  fences, reads the value. Either the consumer sees the new value, or the producer sees the flag
  clear and queues the index again. The fences are full ones (store then load needs it); on one
  core they cost little and they are what batch 11 needs when the producer moves to the M4.
- Smoothing stays on the audio side, by the parameter's `smooth_ms` (batch 8c).

## Numbers

| Measurement | Value | Test |
|---|---|---|
| Parameters | 169 of 192 | `test_table_rules` |
| 10 000 random writes, no consumer | newest value of each arrives once; ring never above 192 | `test_burst_keeps_the_newest_value_and_never_overflows` |
| Curves against the float64 reference, 8 positions, every parameter | within 1e-5 relative | `test_curves_match_the_reference` |
| M7 image with `ctl/` | 67.2 KB flash, 64.9 KB DTCM (was 42.8 and 57) | `cmake --build --preset fw` |
| Cycles to drain the queue in the audio interrupt | not measured (needs batch 2's interrupt) | |

## From the transcripts

`transcripts_index.md` lists no transcript for batch 8a, and none of the 29 covers parameter
registries, control protocols, MIDI or flash storage. All 29 were searched for how the videos
handle controls:
- #117 and #153 sample the pedal's potentiometers with a separate ADC and map them straight onto
  the effect's settings (gain, filters, output volume). One writer, so no registry is needed.
- #58 updates a setting only when its pot has moved by more than 1 % ("so we don't get too much
  jitter"), with 5 % mentioned as the alternative.
Differs, and why: this device has four writers (knobs, PC, MIDI, presets), so every write goes
through the registry and reaches the audio level only through the queue. Agrees: the 1 %
threshold is the same figure as the pick-up hysteresis here (`knob_pickup.md`).

## The budget rule

Measured on the board (`docs/results/budget_target.md`), the overdrive and the strips'
saturation cannot both run within the CPU budget. `ctl_core_set` refuses turning either on while
the other runs (`kCtlErrBudget`, protocol error 10), from any source; a preset holding both loads
everything else and counts the refusal. The panel (batch 8d) should step past the overdrive
while a strip saturates rather than show a refusal.

## Open questions

- Per-parameter smoothing times are guesses (20 ms for gains and frequencies). Batch 8c measures
  zipper noise and sets them.
- The PEQ band types are fixed (shelf, peak, peak, shelf). A type parameter per band is cheap to
  add later under the reserved ids.
