"""The budget rule (owner, 2026-11-18): the effect slot and the strips' saturation never run
together. It replaced the overdrive-only rule of 2026-11-17."""
import ctllib

ERR_BUDGET = 10
OVERDRIVE = 6


def test_ids_in_the_rule_are_the_table_s(ctl):
    for name, pid in (("in1_sat_on", 150), ("in2_sat_on", 250), ("fx_on", 401)):
        assert ctl.ctl_param_desc(ctl.ctl_param_find(name.encode(), len(name))).contents.id == pid


def test_strip_saturation_refused_while_any_effect_runs(dev):
    for fx in range(8):
        assert dev.set("fx_select", fx) == ctllib.OK
        assert dev.set("fx_on", 1) == ctllib.OK
        for name in ("in1_sat_on", "in2_sat_on"):
            assert dev.set(name, 1) == ERR_BUDGET, f"effect {fx}"
            assert dev.get(name) == 0.0
        assert dev.set("fx_on", 0) == ctllib.OK
    assert dev.cmd("set fx_on 1")[0].startswith("ok")
    assert dev.cmd("set in1_sat_on 1")[0].startswith("err 10 budget")
    assert dev.set("fx_on", 0) == ctllib.OK
    assert dev.set("in1_sat_on", 1) == ctllib.OK, "free again once the slot is off"


def test_effect_slot_refused_while_a_strip_saturates(dev):
    dev.set("in2_sat_on", 1)
    for src in (ctllib.SRC_PC, ctllib.SRC_BUTTON, ctllib.SRC_MIDI):
        assert dev.set("fx_on", 1, src) == ERR_BUDGET
    assert dev.get("fx_on") == 0.0
    assert dev.set("in2_sat_on", 0) == ctllib.OK
    assert dev.set("fx_on", 1) == ctllib.OK


def test_choosing_the_effect_and_turning_off_are_never_refused(dev):
    dev.set("in1_sat_on", 1)
    for fx in range(8):
        assert dev.set("fx_select", fx) == ctllib.OK, "the slot is off: any choice is fine"
    assert dev.set("in1_sat_on", 0) == ctllib.OK
    dev.set("fx_on", 1)
    for fx in range(8):
        assert dev.set("fx_select", fx) == ctllib.OK, "no strip saturates: any choice is fine"
    assert dev.set("fx_on", 0) == ctllib.OK


def test_a_preset_with_both_loads_the_rest_and_reports_it(dev):
    dev.set("in1_sat_on", 1)
    dev.set("in1_trim_db", 4.0)
    assert dev.save(0) == 0
    dev.set("in1_sat_on", 0)
    dev.set("fx_select", OVERDRIVE)
    dev.set("fx_on", 1)
    final, _ = dev.cmd("preset load 1")
    # in1_sat_on is refused (the slot runs); the five knob parameters are refused too.
    assert final == "ok preset load 1 refused=6"
    assert dev.get("in1_sat_on") == 0.0 and dev.get("in1_trim_db") == 4.0
