"""dsp_tone_f32: exactly flat at centre, the right response, smooth changes, clean skipping."""
import ctypes

import numpy as np
import pytest

import dsplib
from ref import tone as ref

FS = 48000.0
BLOCK = 16


def make(lib, fs=FS, gains=(0.0, 0.0, 0.0), settle=True):
    tone = dsplib.DspToneF32()
    lib.dsp_tone_f32_init(ctypes.byref(tone), fs)
    for band, gain in enumerate(gains):
        lib.dsp_tone_f32_set_db(ctypes.byref(tone), band, gain)
    if settle:
        lib.dsp_tone_f32_reset(ctypes.byref(tone))
    return tone


def run(lib, tone, left, right=None, block=BLOCK, on_block=None):
    right = left if right is None else right
    out_l = np.zeros_like(left)
    out_r = np.zeros_like(right)
    for i in range(0, len(left), block):
        if on_block:
            on_block(i)
        l_in, r_in = left[i:i + block].copy(), right[i:i + block].copy()
        l_out, r_out = np.zeros_like(l_in), np.zeros_like(r_in)
        lib.dsp_tone_f32_process(ctypes.byref(tone), dsplib.f32(l_in), dsplib.f32(r_in),
                                 dsplib.f32(l_out), dsplib.f32(r_out), len(l_in))
        out_l[i:i + block], out_r[i:i + block] = l_out, r_out
    return out_l, out_r


def noise(n, seed=1, scale=0.25):
    return (np.random.default_rng(seed).uniform(-1, 1, n) * scale).astype(np.float32)


def response_db(h, fs, freqs):
    n = np.arange(len(h))
    return np.array([20 * np.log10(abs(np.sum(h * np.exp(-2j * np.pi * f * n / fs))))
                     for f in freqs])


def test_flat_at_centre_is_bit_exact(lib):
    x = noise(4096)
    y_l, y_r = run(lib, make(lib), x, -x)
    assert y_l.tobytes() == x.tobytes() and y_r.tobytes() == (-x).tobytes()


@pytest.mark.parametrize("fs", [48000.0, 96000.0])
@pytest.mark.parametrize("gains", [(12.0, 0.0, 0.0), (-12.0, 0.0, 0.0), (0.0, 6.0, 0.0),
                                   (0.0, -6.0, 0.0), (0.0, 0.0, 12.0), (0.0, 0.0, -12.0),
                                   (6.0, -3.0, 9.0), (-12.0, 12.0, -12.0), (12.0, 12.0, 12.0),
                                   (3.0, 0.0, -6.0), (-6.0, -6.0, -6.0)])
def test_static_response(lib, fs, gains):
    n = 16384
    impulse = np.zeros(n, dtype=np.float32)
    impulse[0] = 0.5
    h, _ = run(lib, make(lib, fs, gains), impulse)
    freqs = np.geomspace(20.0, min(20000.0, 0.45 * fs), 31)
    got = response_db(h.astype(np.float64) / 0.5, fs, freqs)
    expected = ref.magnitude_db(fs, gains, freqs)
    assert np.max(np.abs(got - expected)) < 0.05


def test_channels_are_independent_and_identical(lib):
    x = noise(2048)
    tone = make(lib, gains=(6.0, -3.0, 9.0))
    y_l, y_r = run(lib, tone, x, x)
    assert y_l.tobytes() == y_r.tobytes()
    tone = make(lib, gains=(6.0, -3.0, 9.0))
    y_l2, y_r2 = run(lib, tone, x, np.zeros_like(x))
    assert y_l2.tobytes() == y_l.tobytes() and not np.any(y_r2)


def test_gain_is_clamped(lib):
    tone = make(lib, gains=(30.0, -30.0, 0.0))
    assert list(tone.target_db) == [12.0, -12.0, 0.0]


def test_smoothing_arrives_exactly_and_on_time(lib):
    tone = make(lib)
    lib.dsp_tone_f32_set_db(ctypes.byref(tone), 0, 12.0)
    silent = np.zeros(BLOCK, dtype=np.float32)
    trajectory = []
    for _ in range(600):  # 200 ms at 48 kHz
        run(lib, tone, silent)
        trajectory.append(tone.smoothed_db[0])
    trajectory = np.array(trajectory)
    assert np.all(np.diff(trajectory) >= 0)
    assert trajectory[-1] == 12.0
    # One time constant (20 ms = 60 blocks of 16): 63 % of the way.
    assert abs(trajectory[59] / 12.0 - (1 - np.exp(-1))) < 0.02


def test_moving_gains_match_a_blockwise_reference(lib):
    """Filtering and redesign are checked on identical gains: the reference designs from the
    smoothed gains the C block reports for each block."""
    x = noise(48000, seed=3)
    tone = make(lib)
    model = ref.Blockwise(FS)
    out_ref = np.zeros(len(x))
    schedule = {0: (0, 12.0), 4800: (1, -9.0), 12000: (2, 6.0), 24000: (0, -12.0),
                36000: (1, 0.0)}

    def on_block(i):
        if i in schedule:
            band, gain = schedule[i]
            lib.dsp_tone_f32_set_db(ctypes.byref(tone), band, gain)

    out_c = np.zeros_like(x)
    for i in range(0, len(x), BLOCK):
        on_block(i)
        block = x[i:i + BLOCK].copy()
        y_l, y_r = np.zeros_like(block), np.zeros_like(block)
        lib.dsp_tone_f32_process(ctypes.byref(tone), dsplib.f32(block), dsplib.f32(block),
                                 dsplib.f32(y_l), dsplib.f32(y_r), BLOCK)
        out_c[i:i + BLOCK] = y_l
        gains = [float(g) for g in tone.smoothed_db]
        active = [int(a) for a in tone.active]
        out_ref[i:i + BLOCK] = model.process(block, gains, active)
    dsplib.assert_within_db(out_c, out_ref, -120.0)


def test_returning_to_centre_ends_bit_exact(lib):
    x = noise(48000, seed=4)
    tone = make(lib, gains=(9.0, 0.0, 0.0))
    lib.dsp_tone_f32_set_db(ctypes.byref(tone), 0, 0.0)
    run(lib, tone, x[:24000])  # Half a second: smoothing and the decay are both done.
    assert tone.active[0] == 0
    y, _ = run(lib, tone, x[24000:])
    assert y.tobytes() == x[24000:].tobytes()


def test_leaving_centre_has_no_step(lib):
    """A band that starts from 0 dB begins with cleared state on the identity response, so the
    first block after the change differs from the input only by the tiny first step of gain."""
    t = np.arange(4800)
    x = (0.5 * np.sin(2 * np.pi * 60 * t / FS)).astype(np.float32)
    tone = make(lib)
    changed = {}

    def on_block(i):
        if i == 2400:
            lib.dsp_tone_f32_set_db(ctypes.byref(tone), 0, 12.0)
            changed["at"] = i

    y, _ = run(lib, tone, x, on_block=on_block)
    jump = np.max(np.abs(y[2400:2416].astype(np.float64) - x[2400:2416]))
    assert jump < 0.01  # Under 1 % of a half-scale signal in the first block.


def test_zipper_noise_of_a_full_sweep(lib):
    """A sweep of the bass gain from -12 to +12 dB in 100 ms on a 5 kHz sine (outside the bass
    band) and on a 50 Hz sine: the per-block coefficient steps must not produce sidebands. The
    output is compared with a per-sample (not per-block) redesign in float64; the difference is
    high-passed at 1 kHz for the 50 Hz case and band-stopped around 5 kHz for the other, so only
    the zipper sidebands remain. Measured limit in docs/notes/tone.md."""
    from scipy import signal as sp
    results = {}
    for freq in (50.0, 5000.0):
        n = 9600
        t = np.arange(n)
        x = (0.5 * np.sin(2 * np.pi * freq * t / FS)).astype(np.float32)
        tone = make(lib, gains=(-12.0, 0.0, 0.0))
        gains = []

        def on_block(i):
            if i == 0:
                lib.dsp_tone_f32_set_db(ctypes.byref(tone), 0, 12.0)

        y = np.zeros_like(x)
        for i in range(0, n, BLOCK):
            on_block(i)
            blk = x[i:i + BLOCK].copy()
            yl, yr = np.zeros_like(blk), np.zeros_like(blk)
            lib.dsp_tone_f32_process(ctypes.byref(tone), dsplib.f32(blk), dsplib.f32(blk),
                                     dsplib.f32(yl), dsplib.f32(yr), BLOCK)
            y[i:i + BLOCK] = yl
            gains.append(float(tone.smoothed_db[0]))
        # Per-sample reference: the gain interpolated linearly between block values.
        per_block = np.repeat(gains, BLOCK)
        per_sample = np.interp(t, np.arange(len(gains)) * BLOCK + BLOCK, gains,
                               left=-12.0)
        del per_block
        z = np.zeros(2)
        y_ref = np.zeros(n)
        for i in range(n):
            b0, b1, b2, a1, a2 = ref.coef.low_shelf(FS, 100.0, 1.0, per_sample[i])
            out, z = sp.lfilter([b0, b1, b2], [1, a1, a2], [float(x[i])], zi=z)
            y_ref[i] = out[0]
        diff = y.astype(np.float64) - y_ref
        if freq == 50.0:
            sos = sp.butter(4, 1000.0, "highpass", fs=FS, output="sos")
        else:
            sos = sp.butter(2, [3500.0, 7000.0], "bandstop", fs=FS, output="sos")
        side = sp.sosfilt(sos, diff)[2000:]
        results[freq] = 20 * np.log10(np.sqrt(np.mean(side ** 2)) + 1e-30)
    print(f"zipper sidebands: {results}")
    assert results[50.0] < -100.0 and results[5000.0] < -100.0
