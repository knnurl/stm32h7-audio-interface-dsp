"""ctl_proto: every command, its replies and errors (docs/notes/control_protocol.md), the number
formatting, and the fuzz runs."""
import subprocess
import sys

import numpy as np
import pytest

import ctllib


def test_hello(dev):
    final, data = dev.cmd("hello")
    assert data == []
    assert final.startswith("ok hello proto=1 fw=host unit=0x00c0ffee params=")


def test_list_matches_the_table(dev, ctl):
    final, data = dev.cmd("list")
    n = ctl.ctl_param_count()
    assert final == f"ok list {n}" and len(data) == n
    first = data[0].split(" ", 9)
    assert first[:9] == ["=", "100", "in1_trim_db", "dB", "-20", "20", "0", "lin", "p"]
    assert data[0].endswith("p Input 1 trim")
    flags = {line.split(" ")[2]: line.split(" ")[8] for line in data}
    assert flags["tone_bass_db"] == "kp" and flags["mute"] == "b" and flags["in1_peak_db"] == "r"


@pytest.mark.parametrize("line,reply", [
    ("get tone_mid_hz", "ok tone_mid_hz 1000"),
    ("set tone_mid_hz 2500.5", "ok tone_mid_hz 2500.5"),
    ("set tone_mid_hz 99999", "ok tone_mid_hz 3000"),       # Clamped, and says so.
    ("set fx_select 2.6", "ok fx_select 3"),                # Step: rounded.
    ("set in1_comp_ratio 1e1", "ok in1_comp_ratio 10"),
    ("set in1_trim_db -0.00001", "ok in1_trim_db 0"),
    ("  get   mute  ", "ok mute 1"),                        # Spaces anywhere; outputs start muted.
    ("set in1_peak_db 0", "err 6 read-only"),
    ("set nosuch 1", "err 3 unknown parameter"),
    ("get", "err 1 usage: get <name>"),
    ("set mute", "err 1 usage: set <name> <value>"),
    ("set mute 1 2", "err 1 usage: set <name> <value>"),
    ("set mute one", "err 4 bad value"),
    ("set mute 1e", "err 4 bad value"),
    ("set mute nan", "err 4 bad value"),
    ("mode tone_mid_hz pc", "err 9 parameter has no knob"),
    ("mode tone_mid_db sometimes", "err 4 mode is knob or pc"),
    ("mode blend", "ok mode blend knob attached=0"),
    ("meters on", "ok meters on"),
    ("src mix", "ok src mix"),
    ("src", "ok src inputs"),
    ("tempo 140", "ok tempo 140 source=stored"),
    ("tempo 1000", "ok tempo 300 source=stored"),
    ("frobnicate", "err 2 unknown command"),
    ("HELLO", "err 2 unknown command"),
])
def test_commands(dev, line, reply):
    final, _ = dev.cmd(line)
    assert final == reply


def test_blank_lines_get_no_reply_and_line_endings_mix(dev):
    assert dev.send("\r\n\n\r") == []
    assert dev.send("get mute\r\nget dim\rget blend\n") == ["ok mute 1", "ok dim 0", "ok blend 0.5"]


def test_split_anywhere(dev):
    text = "set tone_mid_hz 1234\n"
    out = []
    for ch in text:
        out += dev.send(ch)
    assert out == ["ok tone_mid_hz 1234"]


def test_line_too_long(dev):
    assert dev.send("get " + "x" * 300 + "\n") == ["err 8 line too long"]
    assert dev.send("get mute\n") == ["ok mute 1"], "the next line is read normally"


def test_presets_over_the_protocol(dev):
    assert dev.cmd("preset list") == ("ok preset list 0", [])
    dev.cmd("set in1_trim_db 6")
    assert dev.cmd("preset save 3 Vocal take")[0] == "ok preset save 3"
    dev.cmd("set in1_trim_db -2")
    assert dev.cmd("preset save 1")[0] == "ok preset save 1"
    final, data = dev.cmd("preset list")
    assert final == "ok preset list 2"
    assert data[0].startswith("= 1 seq=") and data[0].endswith(" preset 1")
    assert data[1].endswith(" Vocal take")
    # The five knobs saved in presets are in knob-wins mode by default: refused, and reported.
    assert dev.cmd("preset load 3")[0] == "ok preset load 3 refused=5"
    assert dev.cmd("get in1_trim_db")[0] == "ok in1_trim_db 6"
    assert dev.cmd("preset name 3 Lead")[0] == "ok preset name 3"
    assert dev.cmd("preset list")[1][1].endswith(" Lead")
    assert dev.cmd("preset load 5")[0].startswith("err 7")
    assert dev.cmd("preset load 9")[0] == "err 4 slot is 1 to 8"
    assert dev.cmd("preset load x")[0] == "err 4 slot is 1 to 8"
    assert dev.cmd("preset frob 1")[0].startswith("err 1")


def test_preset_load_reports_knob_refusals(dev):
    dev.knob("blend", 0.2)  # Knob wins.
    dev.cmd("preset save 2")
    final, _ = dev.cmd("preset load 2")
    # Every knob saved in presets (the three tone gains, fx_amount, blend) is in knob-wins mode.
    assert final == "ok preset load 2 refused=5"
    assert dev.get("blend") == pytest.approx(0.2)


def test_unsolicited_lines(dev):
    dev.knob("fx_amount", 1.0)
    dev.midi([0xB0, 21, 127])  # Mid knob wins: MIDI refused, nothing to report.
    dev.cmd("mode tone_mid_db pc")
    dev.midi([0xB0, 21, 127])
    assert dev.poll() == ["# set fx_amount 1", "# set tone_mid_db 12"]
    dev.cmd("meters on")
    dev.lib.ctl_proto_meters(dev.lib.ctl_host_proto(dev.h))
    line = dev.output()[0]
    assert line.startswith("# meters in1_peak_db=-120 ") and "cpu_load_pct=0" in line


def test_stat(dev):
    dev.cmd("frobnicate")
    final, _ = dev.cmd("stat")
    assert final.startswith("ok stat lines=2 errors=1 ")
    assert "flash_free=" in final


@pytest.mark.parametrize("value,text", [
    (0.0, "0"), (-0.0, "0"), (0.5, "0.5"), (-12.0, "-12"), (20000.0, "20000"), (0.0001, "0.0001"),
    (0.00004, "0"), (1.23456, "1.2346"), (-1.23456, "-1.2346"), (2500.5, "2500.5"),
])
def test_number_formatting(dev, value, text):
    # Formatted through a get of a parameter whose range holds the value.
    name = "crush_rate_hz" if value > 1000 else "in1_trim_db"
    dev.lib.ctl_core_set(dev.core, dev.index(name), value, ctllib.SRC_DEVICE, None)
    assert dev.cmd(f"get {name}")[0] == f"ok {name} {text}"


def test_random_bytes_through_the_library(dev):
    """Quick in-process fuzz; the sanitised run is the next test."""
    rng = np.random.default_rng(9)
    for _ in range(300):
        dev.send(bytes(rng.integers(0, 256, int(rng.integers(1, 400)), dtype=np.uint8)))
        dev.midi(bytes(rng.integers(0, 256, 32, dtype=np.uint8)))
    assert dev.send("\nget mute\n")[-1].startswith("ok mute")


@pytest.mark.skipif(ctllib.fuzz_program() is None, reason="ctl_fuzz not built")
def test_fuzz_under_the_address_sanitiser():
    """ctl_fuzz is built with /fsanitize=address: an out-of-bounds access ends it with a report
    and a non-zero exit."""
    run = subprocess.run([str(ctllib.fuzz_program()), "200000", "11"], capture_output=True,
                         text=True, timeout=300)
    assert run.returncode == 0, run.stdout + run.stderr
    assert run.stdout.startswith("fuzz ok")
