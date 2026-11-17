"""The budget rule: the overdrive and the strips' saturation never run together."""
import ctllib

ERR_BUDGET = 10
OVERDRIVE = 6


def overdrive_on(dev, src=ctllib.SRC_PC):
    assert dev.set("fx_select", OVERDRIVE, src) == ctllib.OK
    return dev.set("fx_on", 1, src)


def test_ids_in_the_rule_are_the_table_s(ctl):
    for name, pid in (("in1_sat_on", 150), ("in2_sat_on", 250), ("fx_on", 401),
                      ("fx_select", 400)):
        assert ctl.ctl_param_desc(ctl.ctl_param_find(name.encode(), len(name))).contents.id == pid


def test_strip_saturation_refused_while_the_overdrive_runs(dev):
    assert overdrive_on(dev) == ctllib.OK
    for name in ("in1_sat_on", "in2_sat_on"):
        assert dev.set(name, 1) == ERR_BUDGET
        assert dev.get(name) == 0.0
    assert dev.cmd("set in1_sat_on 1")[0].startswith("err 10 budget")
    assert dev.set("fx_on", 0) == ctllib.OK
    assert dev.set("in1_sat_on", 1) == ctllib.OK, "free again once the overdrive is off"


def test_overdrive_refused_while_a_strip_saturates(dev):
    dev.set("in2_sat_on", 1)
    assert dev.set("fx_select", OVERDRIVE) == ctllib.OK, "selecting it while the slot is off is fine"
    assert dev.set("fx_on", 1, ctllib.SRC_BUTTON) == ERR_BUDGET
    dev.set("fx_select", 1)
    assert dev.set("fx_on", 1) == ctllib.OK
    assert dev.set("fx_select", OVERDRIVE, ctllib.SRC_MIDI) == ERR_BUDGET, "nor by stepping to it"
    assert dev.get("fx_select") == 1.0


def test_other_effects_and_turning_off_are_never_refused(dev):
    dev.set("in1_sat_on", 1)
    dev.set("fx_on", 1)
    for fx in (0, 1, 2, 3, 4, 5, 7):
        assert dev.set("fx_select", fx) == ctllib.OK
    assert dev.set("fx_select", OVERDRIVE) == ERR_BUDGET, "the slot is on: selecting it is refused"
    assert dev.set("in1_sat_on", 0) == ctllib.OK
    assert dev.set("fx_select", OVERDRIVE) == ctllib.OK, "and allowed once the strip stops"


def test_a_preset_with_both_loads_the_rest_and_reports_it(dev):
    dev.set("in1_sat_on", 1)
    dev.set("in1_trim_db", 4.0)
    assert dev.save(0) == 0
    dev.set("in1_sat_on", 0)
    overdrive_on(dev)
    final, _ = dev.cmd("preset load 1")
    # in1_sat_on is refused (the overdrive runs); the five knob parameters are refused too.
    assert final == "ok preset load 1 refused=6"
    assert dev.get("in1_sat_on") == 0.0 and dev.get("in1_trim_db") == 4.0
