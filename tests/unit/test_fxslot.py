"""dsp_fxslot: transparent when off, no clicks when switching, trails that decay at the set
feedback, and no audio from before a stop ever comes back."""
import ctypes

import numpy as np
import pytest

import dsplib
import dsplib_b8b as b8

FS = 48000.0
POOL = 2 * 24000  # 0.5 s of echo per channel


@pytest.fixture(scope="module")
def lib8(lib):
    return b8.bind(lib)


def make_slot(lib8, pool_len=POOL):
    slot = b8.DspFxSlotF32()
    mem = np.zeros(pool_len, dtype=np.float32)
    rc = lib8.dsp_fxslot_f32_init(ctypes.byref(slot), FS, dsplib.f32(mem), pool_len)
    return b8.WithMemory(slot, mem), rc


def run(lib8, s, x, x_r=None):
    return b8.run_stereo(lib8.dsp_fxslot_f32_process, s.state, x, x_r)


def sine(n, f=1000.0, amp=0.5):
    return (amp * np.sin(2 * np.pi * f * np.arange(n) / FS)).astype(np.float32)


def test_off_is_bit_exact(lib8):
    s, rc = make_slot(lib8)
    assert rc == 0
    x = np.random.default_rng(1).uniform(-1, 1, 9600).astype(np.float32)
    yl, yr = run(lib8, s, x)
    assert yl.tobytes() == x.tobytes() and yr.tobytes() == x.tobytes()


def test_pool_size_sets_the_echo_time(lib8):
    """The smallest pool that holds the chorus gives the echo 28 ms; a pool too small for the
    chorus fails, and leaves the echo unavailable when it is under 10 ms."""
    need = lib8.dsp_fx_chorus_f32_mem_needed(FS)
    s, rc = make_slot(lib8, need)
    assert rc == 0 and s.state.available[b8.FX_CHORUS] == 1
    assert lib8.dsp_fx_echo_f32_max_time_ms(ctypes.byref(s.state.echo)) == \
        pytest.approx((need // 2 - 3) / 48, rel=1e-6)
    s, rc = make_slot(lib8, 100)
    assert rc == -1 and s.state.available[b8.FX_ECHO] == 0


def second_difference_peak(y):
    return float(np.max(np.abs(np.diff(y.astype(np.float64), 2))))


def test_switching_makes_no_click(lib8):
    """A 1 kHz sine at half scale through every change: on, each effect in turn, off. A click
    is a jump the signal itself does not make, which shows in the second difference: the bare
    sine's is 0.5 (2 pi 1000 / 48000)^2 = 0.0086. Each 50 ms segment around a change must stay
    within 1.5 times the larger steady-state value of the effects either side of it."""
    s, _ = make_slot(lib8)
    slot = s.state
    lib8.dsp_fx_overdrive_f32_set_tone(ctypes.byref(slot.overdrive), 0.3)
    lib8.dsp_fxslot_f32_set_amount(ctypes.byref(slot), 0.3)
    seg = int(0.25 * FS)
    order = [b8.FX_ECHO, b8.FX_CHORUS, b8.FX_FLANGER, b8.FX_PHASER, b8.FX_TREMOLO, b8.FX_SWEEP,
             b8.FX_OVERDRIVE, b8.FX_CRUSHER]
    x = sine(seg * (len(order) + 3))
    out = np.zeros_like(x)
    events = []
    pos = 0

    def step(n):
        nonlocal pos
        yl, _ = run(lib8, s, x[pos:pos + n])
        out[pos:pos + n] = yl
        pos += n

    step(seg)  # off
    lib8.dsp_fxslot_f32_set_on(ctypes.byref(slot), 1)
    for fx in order:
        lib8.dsp_fxslot_f32_select(ctypes.byref(slot), fx)
        events.append(pos)
        step(seg)
    lib8.dsp_fxslot_f32_set_trails(ctypes.byref(slot), 0)
    lib8.dsp_fxslot_f32_set_on(ctypes.byref(slot), 0)
    events.append(pos)
    step(len(x) - pos)
    worst = 0.0
    for e in events:
        before = second_difference_peak(out[e - seg // 2:e - 2400])
        after = second_difference_peak(out[e + seg // 2:e + seg - 100])
        during = second_difference_peak(out[e - 100:e + 6000])
        ratio = during / max(before, after, 0.0086)
        worst = max(worst, ratio)
        assert ratio < 1.5, (e // seg, during, before, after)
    print(f"worst transition / steady second difference: {worst:.2f}")


def test_echo_trails_decay_at_the_set_feedback(lib8):
    """Echo at 100 ms, feedback 0.5, bright tone: a 10 ms 1 kHz burst, then the slot is
    switched off with trails on. The repeats carry on, each 0.5 x the filters' gain at 1 kHz
    below the last, and the slot stops itself once the tail is under -100 dBFS for 0.5 s."""
    s, _ = make_slot(lib8)
    slot = s.state
    lib8.dsp_fx_echo_f32_set_time_ms(ctypes.byref(slot.echo), 100.0)
    lib8.dsp_fx_echo_f32_set_feedback(ctypes.byref(slot.echo), 0.5)
    lib8.dsp_fx_echo_f32_set_tone(ctypes.byref(slot.echo), 1.0)
    lib8.dsp_fxslot_f32_set_amount(ctypes.byref(slot), 1.0)
    lib8.dsp_fxslot_f32_set_on(ctypes.byref(slot), 1)
    run(lib8, s, np.zeros(4800, dtype=np.float32))  # clears the pool, fades in
    burst = np.zeros(int(4 * FS), dtype=np.float32)
    burst[:480] = sine(480)
    yl = np.zeros_like(burst)
    yl[:4800], _ = run(lib8, s, burst[:4800])
    lib8.dsp_fxslot_f32_set_on(ctypes.byref(slot), 0)  # trails on by default
    yl[4800:], _ = run(lib8, s, burst[4800:])
    # RMS per repeat: a sample peak of a filtered 1 kHz burst jitters by about 1 %.
    peaks = [np.sqrt(np.mean(yl[k * 4800 + 100:k * 4800 + 4700].astype(np.float64) ** 2))
             for k in range(1, 8)]
    lp = slot.echo.lp[0].a
    hp = slot.echo.hp[0].a
    w = 2 * np.pi * 1000 / FS
    z = np.exp(-1j * w)
    h = abs((1 - lp) / (1 - lp * z)) * abs(hp * (1 - z) / (1 - hp * z))
    ratios = np.array(peaks[1:]) / np.array(peaks[:-1])
    print("repeat ratios:", np.round(ratios, 4), "expected", round(0.5 * h, 4))
    assert np.allclose(ratios, 0.5 * h, rtol=0.01)
    assert lib8.dsp_fxslot_f32_running(ctypes.byref(slot)) == 0
    # Stopped: the dry passes bit for bit again.
    x = sine(480)
    yl2, _ = run(lib8, s, x)
    assert yl2.tobytes() == x.tobytes()


def test_trails_off_fades_and_stops(lib8):
    s, _ = make_slot(lib8)
    slot = s.state
    lib8.dsp_fxslot_f32_set_trails(ctypes.byref(slot), 0)
    lib8.dsp_fxslot_f32_set_on(ctypes.byref(slot), 1)
    run(lib8, s, sine(9600))
    lib8.dsp_fxslot_f32_set_on(ctypes.byref(slot), 0)
    run(lib8, s, sine(int(0.03 * FS) + 32))
    assert lib8.dsp_fxslot_f32_running(ctypes.byref(slot)) == 0


def test_old_audio_never_returns(lib8):
    """Echo with long feedback fed noise, switched to the chorus and back, then on again with
    silence in: the output must be silent, not the old echoes."""
    s, _ = make_slot(lib8)
    slot = s.state
    lib8.dsp_fx_echo_f32_set_feedback(ctypes.byref(slot.echo), 0.9)
    lib8.dsp_fxslot_f32_set_trails(ctypes.byref(slot), 0)
    lib8.dsp_fxslot_f32_set_on(ctypes.byref(slot), 1)
    run(lib8, s, np.random.default_rng(2).uniform(-1, 1, 24000).astype(np.float32))
    silence = np.zeros(int(0.3 * FS), dtype=np.float32)
    lib8.dsp_fxslot_f32_select(ctypes.byref(slot), b8.FX_CHORUS)
    run(lib8, s, silence)
    lib8.dsp_fxslot_f32_select(ctypes.byref(slot), b8.FX_ECHO)
    yl, _ = run(lib8, s, silence)
    late, _ = run(lib8, s, silence)
    assert slot.active == b8.FX_ECHO
    assert np.max(np.abs(late)) == 0.0 and np.max(np.abs(yl[int(0.1 * FS):])) == 0.0


def test_clearing_is_bounded_per_chunk(lib8):
    """No chunk clears more than kDspFxSlotClearPerChunk floats: the echo pool (48000 floats)
    takes 24 chunks of 16 frames, about 8 ms at 48 kHz, before the fade-in starts."""
    s, _ = make_slot(lib8)
    slot = s.state
    lib8.dsp_fxslot_f32_set_on(ctypes.byref(slot), 1)
    chunks = 0
    x = np.zeros(16, dtype=np.float32)
    while not lib8.dsp_fxslot_f32_running(ctypes.byref(slot)):
        run(lib8, s, x)
        chunks += 1
        assert chunks < 1000
    assert chunks == -(-POOL // 2048)  # the last clearing chunk also starts the effect


def test_deterministic(lib8):
    outs = []
    for _ in range(2):
        s, _ = make_slot(lib8)
        lib8.dsp_fxslot_f32_set_on(ctypes.byref(s.state), 1)
        lib8.dsp_fxslot_f32_select(ctypes.byref(s.state), b8.FX_PHASER)
        y, _ = run(lib8, s, np.random.default_rng(3).uniform(-1, 1, 24000).astype(np.float32))
        outs.append(y.tobytes())
    assert outs[0] == outs[1]
