# Design note: knob ownership and pick-up

Batch 8a. `ctl_core_knob`, `ctl_core_set` (SPEC 6.7).

## Purpose

The seven potentiometers (bass, mid, treble, monitor volume, headphone volume, effect amount,
blend) are absolute: their position is a value. The PC, MIDI and presets also write those values.
Without a rule the value jumps whenever a knob is touched after another source moved it, which on
a monitor volume knob is a hazard, not a nuisance.

## The rule

Each knob has a mode parameter (`mode_<name>`, a setting, saved in the power-on record):

- **Knob wins (default).** The knob sets the value. Writes from the PC, MIDI or a preset are
  refused with `err 5`. The PC shows the knob's value.
- **PC wins.** Anything may write. A write from anything but the knob detaches the knob. A
  detached knob re-attaches when its reading reaches the value:
  - it crosses the value between two readings (a fast turn included), or
  - it comes within the hysteresis (1 % of travel) of it.
  If it attached within the hysteresis, the value stays put until the knob has moved more than
  1 % from the pick-up point; after that it follows. So reading noise near the value changes
  nothing, and the value never jumps by more than the knob's own movement plus 1 %.
- **Switching a knob to knob wins** takes the knob's value at once (that is what the mode means);
  if the knob has not been read since start-up, the value stays until its first reading.

Rejected: "value scaling" (the knob moves the value proportionally towards the end stops), used
by some controllers. It never jumps, but the knob's position stops meaning a value, which the
panel's legends promise.

## The hysteresis, and the plan's wording

The plan said "a hysteresis of 1 % so reading noise near the value does not detach it again".
Only a write from another source detaches a knob, so noise cannot detach it; the hysteresis does
its work at the pick-up instead: noise around the value attaches the knob but does not move the
value. The panel's own ADC filter (batch 8d) handles noise on a knob at rest elsewhere.

## Test evidence

| Behaviour | Test |
|---|---|
| Knob wins refuses PC, MIDI and presets, and says why | `test_knob_wins_refuses_the_pc_midi_and_presets` |
| No jump on re-attach, approaching from below and from above; largest step 0.288 dB on a 24 dB range | `test_no_jump_on_re_attach_from_either_side` |
| A turn that crosses the value between two readings re-attaches | `test_fast_turn_crossing_between_two_readings` |
| +/-1 % reading noise at the value: 2000 readings, no change | `test_reading_noise_near_the_value_changes_nothing` |
| Mode change while detached | `test_mode_change_while_detached` |
| A preset recall detaches every PC-wins knob it writes | `test_preset_recall_detaches_every_pc_wins_knob` |
| A restore applies the modes before the values they govern | `test_power_on_record_respects_knob_wins` |

**Bug found while writing the tests:** the mode parameters have higher ids than the knobs they
govern, so a power-on restore applied the volume first, under the old mode, and refused it. The
preset load now applies the mode parameters in a first pass.

## From the transcripts

No transcript covers knob ownership (none is listed for batch 8a; all 29 were searched for pot
handling). The pedal videos (#117, #153) map their pots straight onto the effect's settings: "knob
wins" with no other writer. #58 changes a setting only when its pot moves by more than 1 % "so we
don't get too much jitter" (5 % mentioned as the alternative). Agrees: the same 1 % here, used as
the pick-up hysteresis; the panel's own ADC filter in batch 8d is where #58's version of it
belongs, for a knob at rest.

## Open questions

- Should the PC client show a detached knob's position as well as the value, so the user can see
  where to turn to pick it up? Cheap to add (`# knob <name> <position>` lines).
- Monitor volume in PC-wins mode can leave the knob far below the actual level: worth an LED hint
  on the panel (batch 8d).
