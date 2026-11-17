"""dsp_lfo and dsp_svf: shapes, rate and sync are exact; the SVF matches its model, has the
textbook response, and stays well behaved where a direct-form biquad does not."""
import ctypes
import math

import numpy as np
import pytest

import dsplib
import dsplib_b8b as b8
from ref import coef as coef_ref
from ref import modulation as ref

FS = 48000.0


@pytest.fixture(scope="module")
def lib8(lib):
    return b8.bind(lib)


def make_lfo(lib8, shape, rate=1.0):
    lfo = b8.DspLfoF32()
    lib8.dsp_lfo_f32_init(ctypes.byref(lfo), FS, shape)
    lib8.dsp_lfo_f32_set_rate(ctypes.byref(lfo), rate)
    return lfo


@pytest.mark.parametrize("shape,limit", [(0, 1e-6), (1, 1e-6), (2, 1e-6), (3, 1e-6)])
def test_shapes_match_the_model(lib8, shape, limit):
    lfo = make_lfo(lib8, shape)
    phases = np.arange(0, 2 ** 32, 2 ** 32 // 65536, dtype=np.uint64)
    got = np.array([lib8.dsp_lfo_f32_value_at(ctypes.byref(lfo), int(p)) for p in phases])
    expect = np.array([ref.lfo_value(shape, p / 2 ** 32) for p in phases])
    err = np.max(np.abs(got - expect))
    print(f"shape {shape}: max error {err:.2e}")
    assert err < limit
    assert np.max(np.abs(got)) <= 1.0


def test_sine_peaks_at_exactly_one(lib8):
    lfo = make_lfo(lib8, b8.LFO_SINE)
    assert lib8.dsp_lfo_f32_value_at(ctypes.byref(lfo), 2 ** 30) == 1.0
    assert lib8.dsp_lfo_f32_value_at(ctypes.byref(lfo), 3 * 2 ** 30) == -1.0


@pytest.mark.parametrize("edge", [0.01, 0.05, 0.2])
def test_rounded_square_edge_length(lib8, edge):
    """Each edge lasts `edge` cycles: count the samples strictly between -1 and 1."""
    lfo = make_lfo(lib8, b8.LFO_SQUARE, 10.0)  # 4800 samples per cycle
    lib8.dsp_lfo_f32_set_edge(ctypes.byref(lfo), edge)
    y = np.zeros(4800, dtype=np.float32)
    lib8.dsp_lfo_f32_process(ctypes.byref(lfo), dsplib.f32(y), len(y))
    in_edge = np.count_nonzero(np.abs(y) < 1.0)
    assert abs(in_edge - 2 * edge * 4800) <= 3
    assert np.max(np.abs(np.diff(y.astype(np.float64)))) < 1.05 * math.pi / (edge * 4800)


def test_rate_is_exact_and_deterministic(lib8):
    lfo = make_lfo(lib8, b8.LFO_SINE, 3.7)
    inc = lfo.inc
    assert inc == round(3.7 / FS * 2 ** 32)
    y1 = np.zeros(100000, dtype=np.float32)
    lib8.dsp_lfo_f32_process(ctypes.byref(lfo), dsplib.f32(y1), len(y1))
    assert lfo.phase == (inc * 100000) % 2 ** 32
    lfo2 = make_lfo(lib8, b8.LFO_SINE, 3.7)
    y2 = np.zeros_like(y1)
    lib8.dsp_lfo_f32_process(ctypes.byref(lfo2), dsplib.f32(y2), len(y2))
    assert y1.tobytes() == y2.tobytes()


def test_tempo_and_sync(lib8):
    lfo = make_lfo(lib8, b8.LFO_SINE)
    lib8.dsp_lfo_f32_set_tempo(ctypes.byref(lfo), 120.0, 1.0)  # a cycle per beat: 2 Hz
    assert lfo.inc == round(2.0 / FS * 2 ** 32)
    lib8.dsp_lfo_f32_set_tempo(ctypes.byref(lfo), 150.0, 0.5)  # eighth notes: 5 Hz
    assert lfo.inc == round(5.0 / FS * 2 ** 32)
    # Beat 3.25 with a cycle per beat is a quarter cycle in: the sine's peak.
    lib8.dsp_lfo_f32_sync(ctypes.byref(lfo), 3.25, 1.0, 0.0)
    assert lib8.dsp_lfo_f32_phase(ctypes.byref(lfo)) == pytest.approx(0.25, abs=1e-9)
    # A cycle per bar (4 beats), offset half a cycle (the other channel of an auto-pan).
    lib8.dsp_lfo_f32_sync(ctypes.byref(lfo), 1001.0, 4.0, 0.5)
    assert lib8.dsp_lfo_f32_phase(ctypes.byref(lfo)) == pytest.approx(0.75, abs=1e-9)
    lib8.dsp_lfo_f32_sync(ctypes.byref(lfo), -1.0, 4.0, 0.0)  # before the first beat
    assert lib8.dsp_lfo_f32_phase(ctypes.byref(lfo)) == pytest.approx(0.75, abs=1e-9)


def test_bad_rates_are_safe(lib8):
    lfo = make_lfo(lib8, b8.LFO_SINE)
    for r in (-1.0, math.nan, math.inf, 1e9):
        lib8.dsp_lfo_f32_set_rate(ctypes.byref(lfo), r)
        assert lfo.inc <= 2 ** 31
    lib8.dsp_lfo_f32_set_tempo(ctypes.byref(lfo), 120.0, 0.0)
    assert lfo.inc == 0
    lib8.dsp_lfo_f32_set_phase(ctypes.byref(lfo), math.nan)
    assert lfo.phase == 0


# ---- State-variable filter ---------------------------------------------------------------------

def make_svf(lib8, fc, q, fast=False):
    svf = b8.DspSvfF32()
    lib8.dsp_svf_f32_init(ctypes.byref(svf), FS, fc, q)
    if fast:
        lib8.dsp_svf_f32_set_fast(ctypes.byref(svf), FS, fc, q)
    return svf


def svf_run(lib8, svf, mode, x):
    x = np.ascontiguousarray(x, dtype=np.float32)
    y = np.zeros_like(x)
    lib8.dsp_svf_f32_process(ctypes.byref(svf), mode, dsplib.f32(x), dsplib.f32(y), len(x))
    return y


@pytest.mark.parametrize("mode", [0, 1, 2, 3])
def test_svf_matches_the_model(lib8, mode):
    x = np.random.default_rng(3).uniform(-0.5, 0.5, 4000).astype(np.float32)
    y = svf_run(lib8, make_svf(lib8, 1200.0, 2.0), mode, x)
    dsplib.assert_within_db(y, ref.svf(x, FS, 1200.0, 2.0, mode), -110.0)


def response_db(y, f, start=4000):
    y = y[start:].astype(np.float64)
    t = np.arange(start, start + len(y)) / FS
    basis = np.stack([np.sin(2 * np.pi * f * t), np.cos(2 * np.pi * f * t)], axis=1)
    (a, b), *_ = np.linalg.lstsq(basis, y, rcond=None)
    return 20 * np.log10(np.hypot(a, b) / 0.5)


def test_svf_textbook_response(lib8):
    """Bilinear with exact prewarping: at fc the low-pass and high-pass are at 20 log10(Q), the
    band-pass at 0 dB when its output is scaled by k (v1 peaks at Q), the notch is deep."""
    fc = 2000.0
    t = np.arange(24000) / FS
    x = (0.5 * np.sin(2 * np.pi * fc * t)).astype(np.float32)
    q = 1 / math.sqrt(2)
    assert response_db(svf_run(lib8, make_svf(lib8, fc, q), b8.SVF_LOW, x), fc) == \
        pytest.approx(-3.0103, abs=0.002)
    assert response_db(svf_run(lib8, make_svf(lib8, fc, q), b8.SVF_HIGH, x), fc) == \
        pytest.approx(-3.0103, abs=0.002)
    assert response_db(svf_run(lib8, make_svf(lib8, fc, 4.0), b8.SVF_BAND, x), fc) == \
        pytest.approx(20 * math.log10(4.0), abs=0.002)
    assert response_db(svf_run(lib8, make_svf(lib8, fc, q), b8.SVF_NOTCH, x), fc) < -60.0


def test_fast_g_error(lib8):
    """The Pade tan: error in g and in the resulting cutoff, printed for the header."""
    worst_low = worst_g = worst_fc = 0.0
    for fc in np.linspace(10.0, 0.45 * FS, 2000):
        g = lib8.dsp_svf_fast_g(FS, fc)
        exact = math.tan(math.pi * fc / FS)
        rel = abs(g / exact - 1)
        fc_eff = math.atan(g) * FS / math.pi
        worst_g = max(worst_g, rel)
        worst_fc = max(worst_fc, abs(fc_eff / fc - 1))
        if fc <= 0.25 * FS:
            worst_low = max(worst_low, rel)
    print(f"g error: {worst_low:.2e} below fs/4, {worst_g:.2e} worst; cutoff error {worst_fc:.2e}")
    assert worst_low < 2e-3 and worst_g < 0.035 and worst_fc < 0.004


@pytest.mark.parametrize("pattern", ["jump", "sweep"])
def test_svf_against_biquad_under_modulation(lib8, lib, pattern):
    """Low-pass, Q 5, on half-scale noise; the cutoff jumps between 200 Hz and 8 kHz every 16
    samples (the update period of the effects), or sweeps between them exponentially at 5 Hz. Both filters get new coefficients at the same
    instants and keep their state. The SVF's peak output stays within the static bound below;
    the direct-form biquad's is printed for the design note."""
    rng = np.random.default_rng(4)
    n = 48000
    x = rng.uniform(-0.5, 0.5, n).astype(np.float32)
    q = 5.0
    svf = make_svf(lib8, 200.0, q)
    y_svf = np.zeros(n, dtype=np.float32)
    y_bq = np.zeros(n, dtype=np.float32)
    state = dsplib.DspBiquadStateF32()
    for start in range(0, n, 16):
        if pattern == "jump":
            fc = 200.0 if (start // 16) % 2 == 0 else 8000.0
        else:
            fc = 200.0 * 40.0 ** (0.5 + 0.5 * math.sin(2 * math.pi * 5.0 * start / FS))
        lib8.dsp_svf_f32_set(ctypes.byref(svf), FS, fc, q)
        seg = np.ascontiguousarray(x[start:start + 16])
        out = np.zeros_like(seg)
        lib8.dsp_svf_f32_process(ctypes.byref(svf), b8.SVF_LOW, dsplib.f32(seg), dsplib.f32(out),
                                 16)
        y_svf[start:start + 16] = out
        c = dsplib.DspBiquadCoefsF32(*[np.float32(v) for v in coef_ref.lowpass(FS, fc, q)])
        out2 = np.zeros_like(seg)
        lib.dsp_biquad_f32_section(ctypes.byref(c), ctypes.byref(state), dsplib.f32(seg),
                                   dsplib.f32(out2), 16)
        y_bq[start:start + 16] = out2
    # Static bound: the L1 norm of the 8 kHz filter's impulse response (the larger of the two)
    # times the input's peak, the most any fixed filter of the pair can output.
    imp = np.zeros(4096, dtype=np.float32)
    imp[0] = 1
    l1 = max(np.sum(np.abs(ref.svf(imp, FS, fc, q, 0))) for fc in (200.0, 8000.0))
    bound = l1 * 0.5
    peak_svf = np.max(np.abs(y_svf))
    finite = np.isfinite(y_bq)
    first_bad = int(np.argmin(finite)) if not finite.all() else -1
    peak_bq = np.max(np.abs(y_bq[finite])) if finite.any() else np.inf
    print(f"{pattern}: static bound {bound:.2f}; peak SVF {peak_svf:.2f}; direct-form biquad peak "
          f"{peak_bq:.3g}, first non-finite sample {first_bad}")
    assert peak_svf < bound
