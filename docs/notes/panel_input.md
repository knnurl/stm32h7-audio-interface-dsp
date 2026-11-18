# Design note: the panel input pipeline

Batch 8d, PC side. `ctl/include/ctl/ctl_pot.h`, `ctl_button.h`, `ctl_panel.h`. The firmware's
ADC, DMA and GPIO wiring waits for the panel board or a breadboard (PLAN_BATCHES 8d); everything
here is hardware-free C in `ctl/`, tested on the PC with synthetic ADC and contact streams.

## Purpose

Seven potentiometers, five buttons and a footswitch drive the parameter registry; seven LEDs
show state. The hard requirement is the one a live user notices: a knob nobody touches must
send nothing (no audio change, no MIDI out, no PC traffic), while a knob being turned must still
resolve fine steps. Buttons must give one event per press whatever the contact does.

## Pots

One reading per millisecond per pot, the sum of 16 conversions (the H7's hardware oversampler
gives the sum [Verify on the board]). Then:

1. **Average:** the sum over its full scale (16 x (2^bits - 1)) is the travel, 0 to 1. 12 to
   16-bit conversions both work.
2. **One-pole smoother,** time constant 4 ms. The averaging and the smoother together cut the
   noise of a single conversion by about 11 times (16 averaged: 4 times; the smoother's
   variance factor a/(2 - a) = 0.124 at a = 0.221: another 2.8 times).
3. **Rest detection with hysteresis.** While the knob moves, the reported travel follows the
   smoothed travel in steps of at least 1/4096 (12 bits). When the smoothed travel has stayed
   inside +/- 1/1024 for 50 ms, the knob is at rest: the value is held, and nothing is reported
   until the travel leaves the held point by more than the hysteresis, 0.4 % of travel.
4. **Shape** (`ctl_pot_shape`): a per-unit calibration (the readings at the two stops and the
   centre detent) and the curve kind. The registry's own curve then maps the shaped position
   onto the parameter, through `ctl_core_knob`, so knob ownership and pick-up
   (`knob_pickup.md`) apply unchanged.

### Why rest detection and not plain hysteresis

The plan said "a one-pole smoother and a hysteresis of 0.4 % of travel, so a still knob sends
nothing. At least 10 bits of usable resolution." Two plain forms of hysteresis each fail one
half of that:

- **Report when the travel moves more than 0.4 % from the last report.** A still knob is
  silent, but a slow turn moves in 0.4 % steps: 250 steps over the travel, about 8 bits.
- **A dead band that the output drags along** (output = input -/+ h). Full resolution, but
  after a turn the output sits at the edge of the band, so every new noise peak on that side
  moves it again: a still knob keeps sending, less and less often.

Rest detection keeps the 0.4 % only for leaving rest, where the jump is harmless (0.1 dB on a
tone gain, 0.1 dB at the top of a volume), and follows the knob at 12 bits while it moves.

**Cost, stated:** a crawl slower than about 2 % of travel per second (the rest window per still
time) counts as at rest between moves, so it moves in 0.4 % steps. And after a turn stops,
noise can move the value by a step or two (1/4096 each) during the 50 ms before it rests. Both
are pinned by tests.

### Curves (proposed, for the owner to confirm)

| Knobs | Kind | Shape |
|---|---|---|
| Bass, mid, treble | Centre | +/- 3 % of travel round the calibrated centre gives exactly 0.5 (0 dB through the registry's linear curve); the rest stretched to the ends |
| Monitor, headphones | Volume | The bottom 3 % of the stretched travel is off; above it the registry's audio taper (max + 60 log10(x) dB, which is already silent below about 4.6 %) |
| FX amount, blend | Linear | End zones only |

All kinds have an end zone of 1 % at each stop, so a pot that stops short of its rail still
reaches the end values exactly (0 dB volume, +/-12 dB tone).

The tone detent may not sit at the electrical centre. Batch 7 measures three pots and decides
whether each unit needs a stored calibration; the `CtlPotCal` struct is ready for it, and where
it would be stored (three settings per pot in the registry, or a calibration record in the
preset store) is a question for then.

## Buttons

Sampled once per millisecond. An integrator counts up on a closed sample and down on an open
one, between 0 and 5: pressed at 5, released at 0. So bounce shorter than 5 ms never changes the
state, a single-sample spike never does, and longer bounce does not either as long as the
contact is closed most of the time. Both edges are delayed alike (5 ms after the contact
settles), so the debounced hold equals the contact's closed time and tap intervals pass through
exactly.

Events: press and release on the debounced edges; long once per hold, 600 ms after the press;
short with the release of a press that never became long.

### Mapping (proposed, for the owner to confirm)

| Button | Action |
|---|---|
| FX select | Short press: next effect. Long press: previous. An effect the budget rule refuses (the overdrive while a strip saturates and the slot is on) is skipped, so the button never seems dead |
| FX on | Each press toggles |
| Tap | Each press is a tap, timed at the press. In auto tempo source, the first tap switches the source to "tap or stored", so the tap is heard even while MIDI clock runs, and remembers the tempo it replaced. A long press undoes that: auto again (MIDI clock if present) and the remembered tempo back. A "MIDI clock only" source is left alone |
| Mute, dim | Each press toggles |
| Footswitch | Setting `footswitch_type`: 0, each press toggles FX on (a momentary pedal); 1, FX on follows the contact (a latching pedal, or a momentary one held). Edges only: a pedal latched at power-up switches the effect on with its first debounced press |

A long press of tap is also a tap at its press. A lone tap changes nothing (the follower needs
two), but one within 2 s of an earlier tap does, just before the long press restores the old
tempo; the restore wins.

Buttons write with the button source, so the budget rule refuses what it must (counted in
`CtlPanel.refused`, for the protocol's `stat` later), and their changes go to MIDI out and the PC
like the knobs'.

## LEDs

At about 100 Hz from the main loop, from the input peak meters: signal at -40 dBFS with a 100 ms
hold, clip at -0.5 dBFS with a 300 ms hold; at the threshold counts. Mute, dim and FX on show
their state. The hold is wrap-safe on a 32-bit millisecond counter.

**Needed from batch 8c:** `in1_peak_db` and `in2_peak_db` must be the peak since the last read
(peak-hold over the meter period), not a sample, or a short clip between two LED updates is
missed.

## Numbers

| What | Value | Test |
|---|---|---|
| Still knob, 100 LSB noise per 16-bit conversion plus 20 LSB of 50 Hz hum, 5 positions incl. both ends | 0 reports in 30 minutes after the first 100 ms | `test_still_noisy_knob_sends_nothing_for_30_minutes` |
| Noise margin | Still settles at 400 LSB per conversion | `test_noise_margin` |
| Slow turn, 6 %/s | Monotonic; steps at most 1/1024 after leaving rest; ends within 1/1024 | `test_slow_turn_is_monotonic_with_ten_bit_steps` |
| Full sweep | At least 1024 distinct reported values | `test_full_sweep_resolves_more_than_ten_bits` |
| Flick, 80 % of travel in 40 ms | Within 1/1024 of the end 25 ms after the knob stops | `test_fast_turn_settles_within_25_ms` |
| Move from rest by 2 % | Reported on the next reading | `test_a_move_from_rest_reports_on_the_next_reading` |
| Bounce up to 4 ms, any pattern, 200 seeds | One press, one release | `test_bounce_up_to_4_ms_gives_one_press_and_one_release` |
| Single-sample spikes every 3 ms | No event | `test_single_sample_glitches_change_nothing` |
| Code on the M7 (GCC -O2, not yet linked into the image) | pot 740 B, button 120 B, panel 1885 B; `CtlPanel` 464 B of RAM | `arm-none-eabi-size` on the objects |

The C matches a float32 Python model (`tests/ref/panel.py`) bit for bit on still, slow, fast
and crawl streams, and the debouncer matches its model on random streams.

The knob-to-audio delay (target under 20 ms) is a board measurement: the panel adds one reading
(1 ms) and the smoother's 4 ms time constant; the registry's audio smoothing (20 ms on the
knobs) comes after. Whether the 20 ms target means the first audible change or the end of that
ramp is a question for the owner; the board measurement reports both.

## From the transcripts

No transcript is listed for batch 8d. All 29 were searched for potentiometer, button, footswitch,
debounce and hysteresis; the passages in #1 (introduction), #49 (notch filters), the compressor
video, #162 (all-pass) and #3 (tremolo) were read, and #34 (complementary filter) for its
low-pass smoothing of a noisy sensor.

- **Control rate:** #1 reads the pots with the processor's ADC from a timer at "about 100 hertz
  or kilohertz", because "the control signals don't have to be sampled that often... 100 times a
  second is more than enough", and with no double buffer. Agrees with the approach; this design
  reads at 1 kHz because the debouncer and the 20 ms knob-to-audio target want it, and the
  16-sample average costs nothing with the hardware oversampler.
- **Dead band:** #49 applies "a small dead band... only if we've changed the control by about
  10 percent" so the filter coefficients are not recomputed all the time. That is the plain
  report-on-change hysteresis above, at 25 times the width; it trades resolution for silence,
  which is fine for a notch width and not for a volume knob. Here the audio side smooths every
  change (registry `smooth_ms`), so recomputing on small moves is not a cost worth that trade.
- **Mapping:** the compressor video and #162 map pots straight onto settings (the "knob wins"
  mode of `knob_pickup.md`), and #49 maps a 0 to 1 control linearly onto a range (50 to 1050 for
  a notch width). The registry curves do the same, with log and audio tapers where the
  parameter wants them.
- **Footswitch:** every pedal video turns the effect on and off with a footswitch (#162 uses it
  as a bypass to measure a flat response first). Here it mirrors FX on, with the two pedal
  types as a setting.
- **Smoothing:** #34 low-passes a noisy sensor before using it; the one-pole here is the same
  idea at its simplest.
- Nothing in the transcripts covers debouncing or LED holds.
