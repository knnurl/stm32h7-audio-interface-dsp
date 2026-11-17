"""ctl_params: the table's rules, the curves against the reference model, MIDI scaling, and the
hand-off queue to the audio level."""
import ctypes
import math
import re

import numpy as np
import pytest

import ctllib
from ref import ctl as ref

SNAKE = re.compile(r"^[a-z][a-z0-9]*(_[a-z0-9]+)*$")
UNIT_SUFFIX = {"dB": "_db", "Hz": "_hz", "ms": "_ms", "s": "_s", "%": "_pct", "BPM": "_bpm",
               "deg": "_deg", "bits": "_bits"}


def descs(ctl):
    return [(i, d, d.name.decode(), d.label.decode(), d.unit.decode())
            for i, d in ctllib.params(ctl)]


def test_table_rules(ctl):
    rows = descs(ctl)
    assert 0 < len(rows) <= ctllib.MAX_PARAMS
    ids = [d.id for _, d, *_ in rows]
    assert ids == sorted(ids) and len(set(ids)) == len(ids), "ids ascend and are unique"
    names = [n for _, _, n, _, _ in rows]
    assert len(set(names)) == len(names)
    for i, d, name, label, unit in rows:
        assert SNAKE.match(name), name
        assert label[0].isupper() and not label.endswith("."), label
        assert d.min < d.max, name
        assert d.min <= d.def_ <= d.max, name
        if d.curve == ctllib.CURVE_LOG:
            assert d.min > 0, name
        if d.curve == ctllib.CURVE_STEP:
            assert d.min == int(d.min) and d.max == int(d.max) and d.def_ == int(d.def_), name
        if unit in UNIT_SUFFIX and name != "crush_bits":
            assert name.endswith(UNIT_SUFFIX[unit]), (name, unit)
        assert ctl.ctl_param_index_of(d.id) == i
        assert ctl.ctl_param_find(name.encode(), len(name)) == i
        saved = d.flags & (ctllib.FLAG_PRESET | ctllib.FLAG_SETTING)
        assert not (d.flags & ctllib.FLAG_READ_ONLY and saved), "meters are never saved"


def test_find_rejects_prefixes_and_extensions(ctl):
    assert ctl.ctl_param_find(b"tone_bass", 9) == -1
    assert ctl.ctl_param_find(b"tone_bass_dbx", 13) == -1
    assert ctl.ctl_param_find(b"", 0) == -1
    assert ctl.ctl_param_index_of(65535) == -1


def test_every_knob_has_a_mode_parameter(ctl):
    knobs = [(i, n) for i, d, n, _, _ in descs(ctl) if d.flags & ctllib.FLAG_KNOB]
    assert len(knobs) == 7, "SPEC 6.7: seven potentiometers"
    for i, name in knobs:
        m = ctl.ctl_param_mode_index(i)
        assert m >= 0, name
        mode = ctl.ctl_param_desc(m).contents
        assert mode.name.decode().startswith("mode_") and mode.flags == ctllib.FLAG_SETTING
        assert mode.def_ == 0.0, "knob wins by default"
    for i, d, name, _, _ in descs(ctl):
        if not d.flags & ctllib.FLAG_KNOB:
            assert ctl.ctl_param_mode_index(i) == -1


@pytest.mark.parametrize("x", [0.0, 0.001, 0.1, 0.25, 0.5, 0.75, 0.999, 1.0])
def test_curves_match_the_reference(ctl, x):
    for i, d, name, _, _ in descs(ctl):
        args = (d.curve, d.min, d.max, d.def_)
        want = ref.from_norm(*args, x)
        got = ctl.ctl_param_from_norm(ctypes.byref(d), x)
        assert got == pytest.approx(want, rel=1e-5, abs=1e-4), (name, x)
        back = ctl.ctl_param_to_norm(ctypes.byref(d), got)
        assert back == pytest.approx(ref.to_norm(*args, got), abs=1e-5), (name, x)


def test_round_trip_through_the_curve(ctl):
    xs = np.linspace(0.0, 1.0, 101)
    for i, d, name, _, _ in descs(ctl):
        if d.curve == ctllib.CURVE_STEP:
            continue
        lo_x = 0.0
        if d.curve == ctllib.CURVE_VOL:  # Below this position the value is the floor (silence).
            lo_x = 10 ** ((d.min - d.max) / 60)
        for x in xs[xs > lo_x + 1e-3]:
            v = ctl.ctl_param_from_norm(ctypes.byref(d), float(x))
            assert ctl.ctl_param_to_norm(ctypes.byref(d), v) == pytest.approx(x, abs=2e-5), name


def test_clamp_and_nan(ctl):
    for i, d, name, _, _ in descs(ctl):
        p = ctypes.byref(d)
        assert ctl.ctl_param_clamp(p, d.max + 1e6) == d.max
        assert ctl.ctl_param_clamp(p, d.min - 1e6) == d.min
        assert ctl.ctl_param_clamp(p, math.nan) == d.def_
        assert ctl.ctl_param_from_norm(p, math.nan) == d.min


@pytest.mark.parametrize("cc,x", [(0, 0.0), (64, 0.5), (127, 1.0)])
def test_midi_scaling_at_0_64_127(ctl, cc, x):
    assert ctl.ctl_midi7_to_norm(cc) == x
    for i, d, name, _, _ in descs(ctl):
        got = ctl.ctl_param_from_norm(ctypes.byref(d), ctl.ctl_midi7_to_norm(cc))
        want = ref.from_norm(d.curve, d.min, d.max, d.def_, x)
        assert got == pytest.approx(want, rel=1e-6, abs=1e-4)
    tone = ctl.ctl_param_desc(ctl.ctl_param_find(b"tone_bass_db", 12)).contents
    assert ctl.ctl_param_from_norm(ctypes.byref(tone), ctl.ctl_midi7_to_norm(cc)) == \
        {0: -12.0, 64: 0.0, 127: 12.0}[cc], "the tone gains are flat at 64, exactly"


def test_midi7_round_trip(ctl):
    for v in range(128):
        assert ctl.ctl_midi7_to_norm(v) == pytest.approx(ref.midi7_to_norm(v))
        assert ctl.ctl_norm_to_midi7(ctl.ctl_midi7_to_norm(v)) == v


# ---- The hand-off queue ----------------------------------------------------------------------

def make_queue(ctl):
    q = ctypes.create_string_buffer(ctl.ctl_sizeof_queue())
    ctl.ctl_queue_init(q)
    return q


def pop_all(ctl, q, max_items=1000):
    out = (ctllib.CtlUpdate * max_items)()
    n = ctl.ctl_queue_pop(q, out, max_items)
    return [(out[k].index, out[k].value) for k in range(n)]


def test_update_mirror_size(ctl):
    assert ctypes.sizeof(ctllib.CtlUpdate) == ctl.ctl_sizeof_update()


def test_queue_order_and_values(ctl):
    q = make_queue(ctl)
    for i, v in [(5, 1.0), (9, 2.0), (1, 3.0)]:
        ctl.ctl_queue_push(q, i, v)
    assert pop_all(ctl, q) == [(5, 1.0), (9, 2.0), (1, 3.0)]
    assert pop_all(ctl, q) == []


def test_burst_keeps_the_newest_value_and_never_overflows(ctl):
    """10 000 writes without the consumer running: every parameter's newest value arrives, each
    once, and the ring never holds more than one entry per parameter."""
    q = make_queue(ctl)
    rng = np.random.default_rng(1)
    newest = {}
    for k in range(10000):
        i = int(rng.integers(0, ctllib.MAX_PARAMS))
        v = float(np.float32(rng.standard_normal()))
        ctl.ctl_queue_push(q, i, v)
        newest[i] = v
        assert ctl.ctl_queue_waiting(q) <= ctllib.MAX_PARAMS
    got = pop_all(ctl, q)
    assert len(got) == len(newest)
    assert dict(got) == newest


def test_pop_is_bounded_per_call(ctl):
    q = make_queue(ctl)
    for i in range(100):
        ctl.ctl_queue_push(q, i, float(i))
    first = (ctllib.CtlUpdate * 16)()
    assert ctl.ctl_queue_pop(q, first, 16) == 16
    assert ctl.ctl_queue_waiting(q) == 84
    assert len(pop_all(ctl, q)) == 84


def test_push_after_pop_is_delivered_again(ctl):
    q = make_queue(ctl)
    ctl.ctl_queue_push(q, 3, 1.0)
    assert pop_all(ctl, q) == [(3, 1.0)]
    ctl.ctl_queue_push(q, 3, 2.0)
    assert pop_all(ctl, q) == [(3, 2.0)]
    ctl.ctl_queue_push(q, 999, 1.0)  # Out of range: ignored.
    assert pop_all(ctl, q) == []
