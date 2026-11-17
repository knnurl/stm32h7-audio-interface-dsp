"""ctl_preset on simulated flash: a power cut at every byte of a write and during compaction, a
full sector, a corrupted record, an older record with fewer parameters, the power-on record, and
the record layout against the reference decoder (docs/notes/preset_store.md)."""
import ctypes

import pytest

import ctllib
from ref import ctl as ref

SMALL = 8192  # A small sector fills quickly; the device uses 128 KB.


def mem(dev, sector):
    return ctypes.string_at(dev.lib.ctl_flash_sim_mem(dev.sim, sector), SMALL)


def active_records(dev):
    for s in (0, 1):
        recs = ref.decode_records(mem(dev, s))
        if recs:
            yield s, recs


def test_layout_matches_the_reference(ctl):
    dev = ctllib.Device(ctl, SMALL)
    dev.set("in1_trim_db", 3.5)
    assert dev.save(2, b"Layout") == 0
    recs = ref.decode_records(mem(dev, 0))
    assert len(recs) == 1
    off, slot, seq, name, values, ok = recs[0]
    assert (off, slot, seq, name, ok) == (32, 2, 1, b"Layout", True)
    assert values[100] == 3.5
    n_preset = sum(1 for _, d in ctllib.params(ctl) if d.flags & ctllib.FLAG_PRESET)
    assert len(values) == n_preset
    # The reference encoder writes the same bytes as the C store.
    entries = list(values.items())
    raw = mem(dev, 0)[32:32 + ref.round_word(32 + 8 * len(entries))]
    assert ref.encode_record(2, 1, b"Layout", entries) == raw


def test_last_good_record_wins(dev):
    for v in (1.0, 2.0, 3.0):
        dev.set("in1_trim_db", v)
        dev.save(0)
    dev.set("in1_trim_db", 0.0)
    assert dev.load(0) == 0 and dev.get("in1_trim_db") == 3.0
    assert dev.load(1) == -1, "an empty slot"


def test_power_cut_at_every_byte_of_a_write(ctl):
    """Preset A is saved. Saving B over it is cut after k bytes, for every k. After the reboot the
    slot holds A, or B once every byte of its content is written (the padding to the flash word
    is erased flash already, so a cut inside it still leaves a good record), never anything
    else, and the store still writes."""
    probe = ctllib.Device(ctl, SMALL)
    probe.save(0)
    record_bytes = SMALL - probe.lib.ctl_preset_free_bytes(probe.store) - 32
    _, _, _, _, values, _ = ref.decode_records(mem(probe, 0))[0]
    content_bytes = 16 + 16 + 8 * len(values)
    assert content_bytes <= record_bytes < content_bytes + 32
    for k in range(record_bytes + 1):
        dev = ctllib.Device(ctl, SMALL)
        dev.set("in1_trim_db", 1.0)
        assert dev.save(0) == 0
        dev.set("in1_trim_db", 2.0)
        dev.lib.ctl_flash_sim_cut_after(dev.sim, k)
        result = dev.save(0)
        dev.reboot()
        dev.set("in1_trim_db", 0.0)
        assert dev.load(0) == 0
        expected = 2.0 if k >= content_bytes else 1.0
        assert result == (0 if k >= record_bytes else -1), k
        assert dev.get("in1_trim_db") == expected, k
        dev.set("in1_trim_db", 5.0)
        assert dev.save(0) == 0, k
        dev.reboot()
        dev.load(0)
        assert dev.get("in1_trim_db") == 5.0, k


def fill(dev, slot_values):
    """Saves until the sector has to compact; returns the values last saved per slot."""
    last = {}
    i = 0
    while dev.lib.ctl_preset_free_bytes(dev.store) >= 1100:
        slot = i % len(slot_values)
        dev.set("in1_trim_db", float(slot_values[slot] + i % 7))
        assert dev.save(slot) == 0
        last[slot] = float(slot_values[slot] + i % 7)
        i += 1
    return last


def test_full_sector_compacts_and_keeps_every_slot(ctl):
    dev = ctllib.Device(ctl, SMALL)
    last = fill(dev, [1, 4, 8])
    dev.set("in1_trim_db", -9.0)
    assert dev.save(3) == 0  # Needs room: compacts into sector 1.
    last[3] = -9.0
    for _ in range(3):  # And on, through several compactions, alternating sectors.
        last.update(fill(dev, [1, 4, 8]))
    dev.reboot()
    for slot, value in last.items():
        assert dev.load(slot) == 0
        assert dev.get("in1_trim_db") == value, slot


@pytest.mark.parametrize("cut", list(range(0, 4000, 97)) + ["erase"])
def test_power_cut_during_compaction(ctl, cut):
    dev = ctllib.Device(ctl, SMALL)
    last = fill(dev, [1, 4])
    if cut == "erase":
        dev.lib.ctl_flash_sim_cut_next_erase(dev.sim)
    else:
        dev.lib.ctl_flash_sim_cut_after(dev.sim, cut)
    dev.set("in1_trim_db", -9.0)
    done = dev.save(6) == 0
    dev.reboot()
    for slot, value in last.items():
        assert dev.load(slot) == 0, (cut, slot)
        assert dev.get("in1_trim_db") == value, (cut, slot)
    assert (dev.load(6) == 0) == done
    dev.set("in1_trim_db", 11.0)
    assert dev.save(6) == 0, "the store recovers"
    dev.reboot()
    dev.load(6)
    assert dev.get("in1_trim_db") == 11.0


def test_corrupted_record_falls_back_to_the_previous_one(dev):
    dev.set("in1_trim_db", 1.0)
    dev.save(0)
    dev.set("in1_trim_db", 2.0)
    dev.save(0)
    recs = ref.decode_records(mem(dev, 0))
    flip = recs[1][0] + 16 + 16 + 4  # A value byte inside the second record.
    p = dev.lib.ctl_flash_sim_mem(dev.sim, 0)
    p[flip] ^= 0x40
    dev.reboot()
    dev.load(0)
    assert dev.get("in1_trim_db") == 1.0
    p[recs[0][0] + 20] ^= 0x01  # Corrupt the first as well: the slot is empty now.
    dev.reboot()
    assert dev.load(0) == -1


def test_older_record_with_fewer_and_unknown_parameters(ctl):
    """Written by hand as an older firmware would: one known id, one id this firmware does not
    have. Known: set; unknown: ignored; missing: their defaults."""
    dev = ctllib.Device(ctl, SMALL)
    dev.set("in2_trim_db", 9.0)
    dev.save(1)  # Formats the flash; the hand-made record goes after it.
    rec = ref.encode_record(1, 50, b"old", [(100, -4.0), (999, 1.0)])
    store_free = dev.lib.ctl_preset_free_bytes(dev.store)
    off = SMALL - store_free
    p = dev.lib.ctl_flash_sim_mem(dev.sim, 0)
    for i, b in enumerate(rec):
        p[off + i] = b
    dev.reboot()
    dev.set("in1_comp_ratio", 7.0)
    assert dev.load(1) == 0
    assert dev.get("in1_trim_db") == -4.0
    assert dev.get("in2_trim_db") == 0.0, "missing from the old record: default"
    assert dev.get("in1_comp_ratio") == 4.0
    dev.set("in1_trim_db", 1.0)
    assert dev.save(1) == 0, "the next sequence number follows the old record's"
    dev.reboot()
    dev.load(1)
    assert dev.get("in1_trim_db") == 1.0


def test_power_on_record(dev):
    dev.time(1000)
    dev.set("tone_treble_hz", 12000.0)  # A setting.
    dev.set("in1_trim_db", 4.0)          # A preset parameter.
    dev.set("mute", 0.0)                 # Neither: the outputs start muted.
    dev.lib.ctl_preset_tick(dev.store, dev.core)
    assert dev.lib.ctl_preset_free_bytes(dev.store) == 0, "nothing written before 2 s"
    dev.time(2999)
    dev.lib.ctl_preset_tick(dev.store, dev.core)
    assert dev.lib.ctl_preset_free_bytes(dev.store) == 0
    dev.time(3000)
    dev.lib.ctl_preset_tick(dev.store, dev.core)
    assert dev.lib.ctl_preset_free_bytes(dev.store) > 0
    dev.lib.ctl_preset_tick(dev.store, dev.core)
    writes_after = dev.lib.ctl_preset_free_bytes(dev.store)
    dev.time(10000)
    dev.lib.ctl_preset_tick(dev.store, dev.core)
    assert dev.lib.ctl_preset_free_bytes(dev.store) == writes_after, "written once, not again"
    dev.reboot()
    assert dev.get("tone_treble_hz") == 12000.0
    assert dev.get("in1_trim_db") == 4.0
    assert dev.get("mute") == 1.0
    assert dev.cmd("preset list")[0] == "ok preset list 0", "the power-on record is not a preset"


def test_power_on_record_respects_knob_wins(dev):
    dev.time(0)
    dev.set("mode_monitor_volume", 1.0)
    dev.set("monitor_volume_db", -10.0)
    dev.time(5000)
    dev.lib.ctl_preset_tick(dev.store, dev.core)
    dev.reboot()
    assert dev.get("monitor_volume_db") == -10.0, "PC wins: restored as left"
    dev.set("mode_monitor_volume", 0.0)
    dev.time(9000)
    dev.lib.ctl_preset_tick(dev.store, dev.core)
    dev.reboot()
    assert dev.get("monitor_volume_db") == -40.0, "knob wins: the default until the knob is read"
