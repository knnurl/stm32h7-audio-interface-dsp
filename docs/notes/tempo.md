# Design note: tempo following

Batch 8b.5. `ctl_tempo` (in `ctl/`, beside the control core).

## Purpose

The synced effects (echo, flanger, phaser, tremolo note values) need the tempo of whatever is
playing. Sources: MIDI clock from Ableton over USB MIDI, tap tempo (panel button, footswitch or
CC 31), and the stored `tempo_bpm`.

## Rules

- **Sources.** `tempo_source`: 0 auto (MIDI clock while present, else stored), 1 MIDI only (no
  tempo without a clock), 2 stored only. Present means at least 3 ticks, the last within 0.5 s.
- **Taps set the stored tempo.** The average of the last four intervals (fewer at first); a gap
  over 2 s starts again. Each tap writes `tempo_bpm` like a typed value, so it is saved in
  presets and the PC hears of it. "Tap" and "stored" are therefore one source.
- **Transport.** Start resets the beat position, continue resumes it, stop freezes it; the
  tempo keeps following a clock that runs while stopped. `ctl_tempo_beat_phase` gives the
  position within the beat for phase-locked LFOs.
- **Output**: the read-only `tempo_now_bpm`, and `tempo` on the protocol
  (`ok tempo 128 source=midi stored=120`).

## The estimator

USB full-speed MIDI arrives in 1 ms frames, so each clock tick carries up to +/-1 ms of jitter:
5 % of a tick at 120 BPM. The plan asked for less than 0.1 BPM of wander from that, and a tempo
change followed within one beat. The two pull against each other, so:

- **A least-squares line through the tick times** over up to 96 ticks (four beats). Its slope is
  the tick period. Rejected: the time between the first and last tick of a window, which uses
  two noisy points instead of all of them (about 0.5 BPM of wander over one beat).
- **A second fit over the last 24 ticks** watches for change. When the two differ by more than
  0.6 % (seven standard deviations of the short fit's jitter noise, so it does not fire on
  jitter), the long fit restarts from the last 4 ticks.
- **Settling.** A fit over a few jittered ticks is noisy (about 1.6 BPM at 4 ticks). Until the
  fresh fit has 16 ticks, the one-beat fit is reported instead: it straddles the change but is
  smooth and already moving. Found by the ramp test: without it, the worst error on a ramp was
  1.57 BPM; with it, 1.35.
- Times are 32-bit microseconds, differences taken unsigned, so the counter's wrap is harmless
  (tested across it). A phase query a microsecond before the newest tick's time no longer wraps
  into a huge difference (bug found by the start and stop test).

## Numbers

| Case | Value | Test |
|---|---|---|
| Steady clock, no jitter | exact to 0.01 BPM from the third tick | `test_steady_clock_is_exact` |
| +/-1 ms jitter on every tick, 64 beats, three seeds | worst 0.032, 0.041, 0.035 BPM after four beats | `test_one_millisecond_jitter_moves_it_less_than_0_1_bpm` |
| Step 120 to 140 BPM | within 0.01 BPM one beat after, no jitter; within 0.5 with jitter | `test_a_tempo_step_is_followed_within_one_beat` |
| Ramp 120 to 132 BPM over 16 beats (0.75 BPM per beat), with jitter | worst 1.35 BPM behind; within 0.2 two beats after it ends | `test_a_ramp_is_tracked` |
| Dropout | MIDI at 0.4 s, stored at 0.6 s; the old ticks forgotten on return | `test_dropout_falls_back_to_stored_and_recovers` |
| Tap | 125 BPM from four taps; a lone tap after 2 s changes nothing | `test_tap_tempo` |

On a ramp the line reports the tempo at its window's centre, so it lags; at most two beats of
the ramp (1.5 BPM here). For a synced echo at 120 BPM, 1.35 BPM is 1.1 % of the delay time,
3 ms on a 1/8 note.

## From the transcripts

None of the batch 8 transcripts covers tempo following. #140 mentions a commercial delay pedal
with note-value settings (quarter, dotted eighth) and tap tempo, which agrees with the note-value
parameters here (`echo_note` and the others: 1/2, 1/4, dotted 1/8, 1/8, 1/8 triplet, 1/16). It
does not describe how the tap is measured.

## Open questions for the owner

- **Glide or cross-fade** when a synced delay time changes (8b.5): glide is implemented in the
  echo (a tape-like pitch bend over 50 ms); cross-fade avoids the bend. Your choice.
- For fast tempo rides, a three-beat window would cut the ramp lag by a quarter and still meet
  the jitter figure (about 0.07 BPM worst, estimated); worth trying if you DJ through it.
- The MIDI clock reaches the follower once USB MIDI exists (batch 4); until then only taps and
  the stored tempo work on the board.
