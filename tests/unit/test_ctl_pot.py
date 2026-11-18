"""ctl_pot with synthetic ADC streams: a still knob with noise and hum, slow and fast turns, a
crawl, start-up; the shaping curves; and the C against the reference model
(docs/notes/panel_input.md)."""
import numpy as np
import pytest

import ctllib
from ref import panel as ref

FULL = 16 * 65535  # One reading: 16 conversions of 16 bits.


def stream(travel, noise_lsb=0.0, hum_lsb=0.0, seed=0):
    """Reading sums for a travel per millisecond: Gaussian noise of noise_lsb per conversion (16
    of them summed: 4 times the sigma) plus a 50 Hz hum of hum_lsb per conversion."""
    travel = np.asarray(travel, dtype=np.float64)
    rng = np.random.default_rng(seed)
    t = np.arange(len(travel)) / 1000.0
    s = travel * FULL + rng.normal(0.0, 4.0 * noise_lsb, len(travel))
    s += 16.0 * hum_lsb * np.sin(2 * np.pi * 50.0 * t + 0.3)
    return np.clip(np.round(s), 0, FULL).astype(np.uint32)


def ramp(a, b, ms, hold_before=200, hold_after=300):
    return np.concatenate([np.full(hold_before, a), np.linspace(a, b, ms), np.full(hold_after, b)])


@pytest.fixture
def pot(ctl):
    return ctllib.Pot(ctl)


# ---- Against the reference model ------------------------------------------------------------

@pytest.mark.parametrize("case", ["still", "slow", "fast", "crawl"])
def test_c_matches_the_reference_bit_for_bit(ctl, pot, case):
    travel = {"still": np.full(3000, 0.37), "slow": ramp(0.2, 0.8, 2000),
              "fast": ramp(0.9, 0.1, 40), "crawl": ramp(0.4, 0.42, 2000)}[case]
    sums = stream(travel, noise_lsb=60, hum_lsb=10, seed=3)
    got, rep = pot.run(sums)
    model = ref.Pot(16, ctl.ctl_pot_coef(4.0))
    want, wrep, last = [], [], None
    for s in sums:
        r = model.update(int(s))
        last = model.out if r else last
        want.append(last)
        wrep.append(int(r))
    assert np.array_equal(rep, np.array(wrep, dtype=np.uint8))
    assert np.array_equal(got, np.array(want, dtype=np.float32))


# ---- A knob at rest -----------------------------------------------------------------------

@pytest.mark.parametrize("position", [0.0, 0.003, 0.5, 0.731, 1.0])
def test_still_noisy_knob_sends_nothing_for_30_minutes(pot, position):
    """100 LSB of noise per 16-bit conversion (about 1.5 LSB at 12 bits, worse than the H7's
    datasheet [Verify on the board]) plus 20 LSB of 50 Hz hum: after the first 100 ms, no
    report in 30 minutes."""
    sums = stream(np.full(30 * 60 * 1000, position), noise_lsb=100, hum_lsb=20, seed=7)
    _, rep = pot.run(sums)
    assert rep[0] == 1
    assert rep[100:].sum() == 0


def test_noise_margin(pot):
    """How much noise the rest detection takes: it still settles at 400 LSB per conversion,
    four times the figure above."""
    sums = stream(np.full(60_000, 0.42), noise_lsb=400, seed=11)
    _, rep = pot.run(sums)
    assert rep[1000:].sum() == 0


# ---- Turning --------------------------------------------------------------------------------

def test_slow_turn_is_monotonic_with_ten_bit_steps(pot):
    """0.2 to 0.8 in 10 s (6 % of travel per second) with noise. While it turns, the reported
    travel never goes back and no step is coarser than 1/1024, except the first: leaving rest
    costs the hysteresis (0.4 %). After it stops, noise may move it by a step or two until the
    rest lock (50 ms), then nothing; it ends within 1/1024 of where the knob stopped."""
    travel = ramp(0.2, 0.8, 10_000)
    got, rep = pot.run(stream(travel, noise_lsb=60, seed=1))
    stop = 200 + 10_000
    idx = np.nonzero(rep)[0]
    turning = got[idx[(idx > 200) & (idx <= stop)]]
    steps = np.diff(turning)
    assert (steps >= 0).all()
    assert steps[1:].max() <= 1 / 1024
    assert turning[0] - got[200] <= 0.004 + 1 / 4096
    after = idx[idx > stop]
    assert len(after) <= 5 and (after < stop + 100).all()
    if len(after):
        assert abs(got[after[-1]] - got[stop]) <= 2 / 4096
    assert abs(got[-1] - 0.8) < 1 / 1024


def test_full_sweep_resolves_more_than_ten_bits(pot):
    travel = ramp(0.0, 1.0, 20_000)
    got, rep = pot.run(stream(travel, noise_lsb=30, seed=2))
    assert len(np.unique(got[rep == 1])) >= 1024
    assert got[-1] > 0.999


def test_fast_turn_settles_within_25_ms(pot):
    """A flick from 0.9 to 0.1 in 40 ms: within 1/1024 of the end 25 ms after the knob stops."""
    travel = ramp(0.9, 0.1, 40, hold_before=200, hold_after=300)
    got, rep = pot.run(stream(travel, noise_lsb=60, seed=4))
    stop = 200 + 40
    assert abs(got[stop + 25] - 0.1) < 1 / 1024
    assert rep.sum() < 200  # About one report per reading while moving, at most.


def test_a_move_from_rest_reports_on_the_next_reading(pot):
    """At rest, a step of 2 % of travel is reported on the first reading after it (the smoother
    moves 22 % of the step at once, over the 0.4 % hysteresis): no added delay at the panel."""
    travel = np.concatenate([np.full(500, 0.5), np.full(100, 0.52)])
    got, rep = pot.run(stream(travel))
    assert rep[100:500].sum() == 0
    assert rep[500] == 1


def test_crawl_moves_in_hysteresis_steps(pot):
    """Slower than about 2 % of travel per second the knob counts as at rest between moves, so
    the value moves in steps of the hysteresis (0.4 % of travel: 0.1 dB on a tone gain). Stated
    in the note; this pins it."""
    travel = ramp(0.40, 0.42, 20_000)  # 0.1 % per second
    got, rep = pot.run(stream(travel, noise_lsb=30, seed=5))
    steps = np.diff(got[rep == 1])
    assert steps.max() <= 0.0045
    assert abs(got[-1] - 0.42) < 0.0045


def test_first_reading_is_the_position(pot):
    got, rep = pot.run(stream(np.full(10, 0.25)))
    assert rep[0] == 1 and got[0] == np.float32(round(0.25 * FULL) / FULL)
    assert rep[1:].sum() == 0


def test_twelve_bit_adc(ctl):
    pot = ctllib.Pot(ctl, adc_bits=12)
    full12 = 16 * 4095
    got, rep = pot.run(np.full(100, full12 // 2, dtype=np.uint32))
    assert rep[0] == 1 and abs(got[0] - 0.5) < 1e-4


# ---- Shaping --------------------------------------------------------------------------------

def shape(ctl, travel, kind, cal=(0.0, 0.5, 1.0)):
    c = ctllib.CtlPotCal(*cal)
    return ctl.ctl_pot_shape(ctypes_ref(c), kind, travel)


def ctypes_ref(c):
    import ctypes
    return ctypes.byref(c)


def test_shape_matches_the_reference(ctl):
    for kind in (ref.LINEAR, ref.CENTRE, ref.VOLUME):
        for cal in ((0.0, 0.5, 1.0), (0.02, 0.53, 0.97)):
            for t in np.linspace(-0.01, 1.01, 409):
                assert np.float32(shape(ctl, t, kind, cal)) == ref.shape(t, kind, *cal), (kind, t)


def test_tone_centre_zone_is_exactly_flat(ctl, dev):
    """+/-3 % of travel round the centre gives exactly 0 dB through the registry's curve."""
    desc = ctl.ctl_param_desc(dev.index("tone_bass_db"))
    for t in np.linspace(0.47, 0.53, 61):
        x = shape(ctl, t, ref.CENTRE)
        assert x == 0.5
        assert ctl.ctl_param_from_norm(desc, x) == 0.0
    assert shape(ctl, 0.469, ref.CENTRE) < 0.5 and shape(ctl, 0.531, ref.CENTRE) > 0.5


def test_tone_centre_follows_the_calibration(ctl):
    """A unit whose detent reads 0.53: flat there, and the ends still reach both stops."""
    cal = (0.01, 0.53, 0.99)
    assert shape(ctl, 0.53, ref.CENTRE, cal) == 0.5
    assert shape(ctl, 0.505, ref.CENTRE, cal) == 0.5
    assert shape(ctl, 0.01, ref.CENTRE, cal) == 0.0
    assert shape(ctl, 0.99, ref.CENTRE, cal) == 1.0


@pytest.mark.parametrize("kind", [ref.LINEAR, ref.CENTRE, ref.VOLUME])
def test_curves_reach_both_ends_and_are_monotonic(ctl, kind):
    ys = [shape(ctl, t, kind) for t in np.linspace(0, 1, 2001)]
    assert ys[0] == 0.0 and ys[-1] == 1.0
    assert shape(ctl, 0.009, kind) == 0.0 and shape(ctl, 0.991, kind) == 1.0
    assert all(b >= a for a, b in zip(ys, ys[1:]))


def test_volume_bottom_is_off(ctl, dev):
    desc = ctl.ctl_param_desc(dev.index("monitor_volume_db"))
    for t in (0.0, 0.02, 0.039):
        assert shape(ctl, t, ref.VOLUME) == 0.0
        assert ctl.ctl_param_from_norm(desc, 0.0) == desc.contents.min
    assert shape(ctl, 0.045, ref.VOLUME) > 0.03
    assert ctl.ctl_param_from_norm(desc, shape(ctl, 1.0, ref.VOLUME)) == 0.0
