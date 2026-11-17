"""ctl_tempo with synthetic MIDI clock: steady, jittered, a tempo step, a ramp, start and stop, a
dropout; and tap tempo (docs/notes/tempo.md)."""
import numpy as np
import pytest

import ctllib


def tick_times(bpm_of_beat, beats, start_us=1_000_000, jitter_us=0.0, seed=0):
    """Exact tick times for a tempo given per beat (a function of the beat index), plus uniform
    jitter of +/- jitter_us on each tick."""
    rng = np.random.default_rng(seed)
    times, t = [], float(start_us)
    for b in range(beats):
        period = 60e6 / bpm_of_beat(b) / 24
        for _ in range(24):
            times.append(t)
            t += period
    times = np.array(times)
    return times + rng.uniform(-jitter_us, jitter_us, len(times)), times


def follow(dev, times, every=1):
    """Feeds the ticks; returns the followed tempo after each tick."""
    out = []
    for i, t in enumerate(times):
        dev.tick(int(round(t)))
        if i % every == 0:
            dev.update(int(round(t)))
            out.append(dev.get("tempo_now_bpm"))
    return np.array(out)


def test_steady_clock_is_exact(dev):
    noisy, _ = tick_times(lambda b: 128.0, 16)
    bpm = follow(dev, noisy)
    assert np.all(np.abs(bpm[3:] - 128.0) < 0.01)
    assert dev.cmd("tempo")[0] == "ok tempo 128 source=midi stored=120"


@pytest.mark.parametrize("seed", [1, 2, 3])
def test_one_millisecond_jitter_moves_it_less_than_0_1_bpm(dev, seed):
    """USB MIDI arrives in 1 ms frames: +/-1 ms on every tick."""
    noisy, _ = tick_times(lambda b: 120.0, 64, jitter_us=1000.0, seed=seed)
    bpm = follow(dev, noisy)
    settled = bpm[4 * 24:]  # After four beats the long fit is full.
    worst = float(np.max(np.abs(settled - 120.0)))
    print(f"seed {seed}: worst {worst:.4f} BPM")
    assert worst < 0.1


@pytest.mark.parametrize("jitter_us,tolerance", [(0.0, 0.01), (1000.0, 0.5)])
def test_a_tempo_step_is_followed_within_one_beat(dev, jitter_us, tolerance):
    noisy, _ = tick_times(lambda b: 120.0 if b < 8 else 140.0, 16, jitter_us=jitter_us, seed=4)
    bpm = follow(dev, noisy)
    one_beat_after = 8 * 24 + 24
    assert abs(bpm[one_beat_after] - 140.0) < tolerance
    assert np.all(np.abs(bpm[one_beat_after:] - 140.0) < tolerance)


def test_a_ramp_is_tracked(dev):
    """120 to 132 BPM over 16 beats, then steady: a fast DJ tempo ride (0.75 BPM per beat).
    A least-squares line over the window reports the tempo at the window's centre, so on a ramp
    it lags: never by more than the two beats from the newest tick to the centre of a full
    four-beat window, 1.5 BPM here; the restarts keep it to less. The measured worst case is
    printed (docs/notes/tempo.md)."""
    def bpm_of(b):
        return 120.0 + min(b, 16) * 0.75
    noisy, _ = tick_times(bpm_of, 24, jitter_us=1000.0, seed=5)
    bpm = follow(dev, noisy)
    # Tick i ends the interval that started at tick i - 1: that interval's tempo is the truth.
    interval_bpm = np.repeat([bpm_of(b) for b in range(24)], 24)
    truth = np.concatenate([[interval_bpm[0]], interval_bpm[:-1]])
    err = np.abs(bpm - truth)[48:]
    print(f"ramp: worst error {err.max():.3f} BPM")
    assert err.max() < 2 * 0.75
    assert np.all(np.abs(bpm[-48:] - 132.0) < 0.2)


def test_dropout_falls_back_to_stored_and_recovers(dev):
    dev.set("tempo_bpm", 100.0)
    noisy, _ = tick_times(lambda b: 140.0, 4)
    follow(dev, noisy)
    last = int(noisy[-1])
    dev.update(last + 400_000)
    assert dev.get("tempo_now_bpm") == pytest.approx(140.0, abs=0.01), "0.4 s: still MIDI"
    dev.update(last + 600_000)
    assert dev.get("tempo_now_bpm") == 100.0, "0.6 s without a tick: the stored tempo"
    resumed, _ = tick_times(lambda b: 90.0, 2, start_us=last + 2_000_000)
    bpm = follow(dev, resumed)
    assert abs(bpm[-1] - 90.0) < 0.01, "the old ticks are forgotten"


def test_start_stop_continue_and_beat_phase(dev):
    noisy, _ = tick_times(lambda b: 120.0, 4)
    period = 60e6 / 120 / 24
    follow(dev, noisy[:10])
    tempo = dev.lib.ctl_host_tempo(dev.h)
    assert dev.lib.ctl_tempo_beat_phase(tempo, int(noisy[9])) == -1.0, "not running"
    dev.tick(int(noisy[10]) - 1, 0xFA)  # Start just before the next tick.
    follow(dev, noisy[10:16])  # Six ticks: a quarter of a beat.
    phase = dev.lib.ctl_tempo_beat_phase(tempo, int(noisy[15] + period / 2))
    assert phase == pytest.approx((5 + 0.5) / 24, abs=1e-3)
    dev.tick(int(noisy[16]), 0xFC)  # Stop: no phase.
    assert dev.lib.ctl_tempo_beat_phase(tempo, int(noisy[16])) == -1.0
    follow(dev, noisy[16:22])  # Clock keeps running while stopped: the tempo stays MIDI.
    assert dev.get("tempo_now_bpm") == pytest.approx(120.0, abs=0.01)
    dev.tick(int(noisy[22]) - 1, 0xFB)  # Continue: from the stopped position.
    follow(dev, noisy[22:24])
    phase = dev.lib.ctl_tempo_beat_phase(tempo, int(noisy[23]))
    assert phase == pytest.approx(7 / 24, abs=1e-3)


def test_source_modes(dev):
    dev.set("tempo_bpm", 100.0)
    noisy, _ = tick_times(lambda b: 140.0, 2)
    follow(dev, noisy)
    dev.set("tempo_source", 2)  # Tap or stored only.
    dev.update(int(noisy[-1]))
    assert dev.get("tempo_now_bpm") == 100.0
    dev.set("tempo_source", 1)  # MIDI only.
    dev.update(int(noisy[-1]) + 600_000)
    assert dev.get("tempo_now_bpm") == 0.0, "no clock, no tempo"


def test_tap_tempo(dev):
    t0 = 5_000_000
    for dt in (0, 480_000, 960_000, 1_440_000):  # 125 BPM (the default is 120).
        dev.midi([0xB0, 31, 127])
        dev.update(t0 + dt)
    assert dev.get("tempo_bpm") == pytest.approx(125.0, abs=0.01)
    assert dev.poll()[-1] == "# set tempo_bpm 125", "the PC hears of a tapped tempo"
    # A gap over 2 s starts again; one tap alone changes nothing.
    dev.midi([0xB0, 31, 127])
    dev.update(t0 + 4_000_000)
    assert dev.get("tempo_bpm") == pytest.approx(125.0, abs=0.01)
    for dt in (4_400_000, 4_800_000):  # 150 BPM.
        dev.midi([0xB0, 31, 127])
        dev.update(t0 + dt)
    assert dev.get("tempo_bpm") == pytest.approx(150.0, abs=0.01)


def test_tap_averages_the_last_four_intervals(dev):
    tempo = dev.lib.ctl_host_tempo(dev.h)
    times = [0, 500_000, 1_000_000, 1_500_000, 2_000_000, 2_400_000]
    results = [dev.lib.ctl_tempo_tap(tempo, 10_000_000 + t) for t in times]
    assert results[0] == 0.0
    # The last four intervals: 0.5, 0.5, 0.5, 0.4 s; mean 0.475 s.
    assert results[-1] == pytest.approx(60 / 0.475, rel=1e-6)


def test_clock_wraps_at_32_bits(dev):
    noisy, _ = tick_times(lambda b: 125.0, 8, start_us=2**32 - 1_000_000)
    bpm = follow(dev, noisy)
    assert np.all(np.abs(bpm[3:] - 125.0) < 0.01)
