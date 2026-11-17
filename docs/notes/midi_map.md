# Design note: the MIDI map

Batch 8a. `ctl_midi`. For review by the owner (the plan's stop for batch 8a).

## Purpose

USB MIDI lets Ableton (or a hardware controller) move the device's controls, and lets Ableton's
MIDI map learn them, because a knob turned on the panel sends its control change.

## Choices

- **Undefined CC numbers only**: 3, 9, 14, 15, 20 to 31, 85 to 90, 102 to 119 (the MIDI 1.0
  table leaves them undefined [Verify against the MIDI Association's current table]). A DAW's
  own meaning of volume (7), pan (10), sustain (64) or bank select (0, 32) never lands on the
  device. That gives 40 numbers; the map uses all 40.
- **Not every parameter has a CC.** There are 169 parameters and 40 free numbers. The panel's
  controls, the mixer, the strips' most-used settings and one or two per effect have one;
  everything else is reachable from the PC. NRPN would cover all of them (open question).
- **Scaling**: 0 to 127 along the parameter's curve, with 64 exactly at the centre
  (`ctl_midi7_to_norm`: below 64 by 1/128, above by 1/126), so the tone gains are flat at 64 and a
  pan is centred.
- **Channel**: `midi_channel`, default 1, 0 for omni. Out goes on the channel (channel 1 in omni).
- **MIDI counts as the PC** for knob ownership: refused while a knob wins.
- **Out**: knob and button changes only, when `midi_cc_out` is on; a value that arrived by MIDI
  is never echoed, so a DAW's feedback loop cannot form.
- **Program change 0 to 7** recalls presets 1 to 8.
- **Clock, start, continue, stop** are counted, time-stamped and passed to the tempo follower
  (batch 8b.5). CC 31 at 64 or more is a tap.

## The map

| CC | Parameter | CC | Parameter |
|---|---|---|---|
| 3 | `record_source` | 85 | `usb_level_db` |
| 9 | `fx_trails` | 86 | `rev_return_db` |
| 14 | `in1_level_db` | 87 | `in1_rev_send_db` |
| 15 | `in2_level_db` | 88 | `in2_rev_send_db` |
| 20 | `tone_bass_db` (fine: 52) | 89 | `usb_rev_send_db` |
| 21 | `tone_mid_db` (fine: 53) | 90 | `rev_decay_s` |
| 22 | `tone_treble_db` (fine: 54) | 102 | `in1_trim_db` |
| 23 | `monitor_volume_db` | 103 | `in2_trim_db` |
| 24 | `phones_volume_db` | 104 | `in1_comp_threshold_db` |
| 25 | `fx_amount` | 105 | `in2_comp_threshold_db` |
| 26 | `blend` | 106 | `in1_sat_drive_db` |
| 27 | `fx_select` | 107 | `in2_sat_drive_db` |
| 28 | `fx_on` | 108 | `in1_pan` |
| 29 | `mute` | 109 | `in2_pan` |
| 30 | `dim` | 110 | `echo_feedback` |
| 31 | tap tempo (an action) | 111 | `echo_time_ms` |
| | | 112 | `chorus_rate_hz` |
| | | 113 | `flanger_feedback` |
| | | 114 | `phaser_rate_hz` |
| | | 115 | `trem_rate_hz` |
| | | 116 | `sweep_resonance` |
| | | 117 | `drive_level_db` |
| | | 118 | `crush_bits` |
| | | 119 | `rev_predelay_ms` |

The fine halves of 20 to 22 are exercise EX8a (`docs/exercises/EX8a_cc14.md`).

## The parser

Running status; real-time bytes anywhere, even inside another message, without disturbing it;
system exclusive skipped to F7 or to the next status byte; system common cancels running status
and its data bytes are skipped; data bytes without a status are dropped; channel mode messages
(CC 120 to 127) ignored.

| Behaviour | Test |
|---|---|
| Every mapped CC undefined in MIDI 1.0, unique, writable; every panel control mapped | `test_map_rules` |
| Running status, three messages after one status byte | `test_running_status` |
| Clock, start and stop inside a control change | `test_realtime_bytes_inside_a_message` |
| System exclusive of 500 bytes with a clock inside; sysex cut by a status byte | `test_system_exclusive_is_skipped` |
| Channel filter and omni | `test_channel_filter_and_omni` |
| Scaling at 0, 64 and 127 for every curve | `test_midi_scaling_at_0_64_127` |
| Not echoed; follows the channel; off switch | `test_cc_out_for_knobs_and_buttons_not_echoed` |

## From the transcripts

No transcript covers MIDI (none is listed for batch 8a).

## Open questions for the owner

- Is this the right set of 40? The candidates left out: the strip gates and the PEQ, every
  effect's second parameter, the speaker and headphone stages.
- NRPN for the rest (CC 99, 98, 6, 38): every parameter by id, at 14 bits. Ableton's MIDI map
  does not learn NRPN [Verify], so it would serve hardware controllers and scripts only.
- MIDI learn (SPEC 6.7 says "later").
