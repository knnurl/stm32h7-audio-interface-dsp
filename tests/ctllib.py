"""The C control library (ctl/), loaded through ctypes. Structures stay opaque: the tests reach
them through the library's functions, so nothing but CtlUpdate is mirrored here.

Build first: `cmake --preset host`, `cmake --build --preset host-release`.
"""
import ctypes
import pathlib

ROOT = pathlib.Path(__file__).resolve().parent.parent

c_float, c_int, c_int32, c_uint8, c_uint16, c_uint32, c_size, c_void_p, c_char_p = (
    ctypes.c_float, ctypes.c_int, ctypes.c_int32, ctypes.c_uint8, ctypes.c_uint16,
    ctypes.c_uint32, ctypes.c_size_t, ctypes.c_void_p, ctypes.c_char_p)

FLAG_KNOB, FLAG_BUTTON, FLAG_PRESET, FLAG_SETTING, FLAG_READ_ONLY = 1, 2, 4, 8, 16
CURVE_LIN, CURVE_LOG, CURVE_VOL, CURVE_STEP = 0, 1, 2, 3
SRC_KNOB, SRC_BUTTON, SRC_PC, SRC_MIDI, SRC_PRESET, SRC_DEVICE = range(6)
OK, ERR_KNOB_WINS, ERR_READ_ONLY, ERR_NOT_KNOB = 0, 5, 6, 9
MAX_PARAMS = 192


class CtlParamDesc(ctypes.Structure):
    _fields_ = [("id", c_uint16), ("curve", c_uint8), ("flags", c_uint8), ("name", c_char_p),
                ("label", c_char_p), ("unit", c_char_p), ("min", c_float), ("max", c_float),
                ("def_", c_float), ("smooth_ms", c_float)]


class CtlUpdate(ctypes.Structure):
    _fields_ = [("index", c_uint16), ("value", c_float)]


class CtlPotCal(ctypes.Structure):
    _fields_ = [("lo", c_float), ("centre", c_float), ("hi", c_float)]


POT_LINEAR, POT_CENTRE, POT_VOLUME = 0, 1, 2
PRESS, RELEASE, LONG, SHORT = 1, 2, 4, 8
POTS = ("tone_bass_db", "tone_mid_db", "tone_treble_db", "monitor_volume_db", "phones_volume_db",
        "fx_amount", "blend")
BTN_FX_SELECT, BTN_FX_ON, BTN_TAP, BTN_MUTE, BTN_DIM, BTN_FOOTSWITCH = range(6)
LED_SIGNAL1, LED_CLIP1, LED_SIGNAL2, LED_CLIP2, LED_MUTE, LED_DIM, LED_FX_ON = (1 << k for k in range(7))


class CtlMidiMapEntry(ctypes.Structure):
    _fields_ = [("cc", c_uint8), ("param_id", c_uint16)]


def find_library(name="ctl_host"):
    for path in (ROOT / f"build/host/ctl/Release/{name}.dll", ROOT / f"build/host/ctl/{name}.dll",
                 ROOT / f"build/host/ctl/lib{name}.so"):
        if path.exists():
            return path
    raise FileNotFoundError("Build first: cmake --preset host, cmake --build --preset host-release")


def fuzz_program():
    for path in (ROOT / "build/host/ctl/Release/ctl_fuzz.exe", ROOT / "build/host/ctl/ctl_fuzz"):
        if path.exists():
            return path
    return None


def load():
    lib = ctypes.CDLL(str(find_library()))
    P = ctypes.POINTER

    def sig(name, restype, *argtypes):
        fn = getattr(lib, name)
        fn.restype = restype
        fn.argtypes = list(argtypes)

    sig("ctl_param_count", c_size)
    sig("ctl_param_desc", P(CtlParamDesc), c_size)
    sig("ctl_param_find", c_int32, c_char_p, c_size)
    sig("ctl_param_index_of", c_int32, c_uint16)
    sig("ctl_param_mode_index", c_int32, c_size)
    for name in ("ctl_param_clamp", "ctl_param_from_norm", "ctl_param_to_norm"):
        sig(name, c_float, P(CtlParamDesc), c_float)
    sig("ctl_midi7_to_norm", c_float, c_uint8)
    sig("ctl_norm_to_midi7", c_uint8, c_float)

    sig("ctl_queue_init", None, c_void_p)
    sig("ctl_queue_push", None, c_void_p, c_uint16, c_float)
    sig("ctl_queue_pop", c_size, c_void_p, P(CtlUpdate), c_size)
    sig("ctl_queue_waiting", c_uint32, c_void_p)
    sig("ctl_sizeof_update", c_size)
    sig("ctl_sizeof_queue", c_size)

    sig("ctl_core_set", c_int, c_void_p, c_size, c_float, c_int, P(c_float))
    sig("ctl_core_knob", c_int, c_void_p, c_size, c_float)
    sig("ctl_core_get", c_float, c_void_p, c_size)
    sig("ctl_core_mode", c_int, c_void_p, c_size)
    sig("ctl_core_knob_attached", c_int, c_void_p, c_size)
    sig("ctl_core_set_time", None, c_void_p, c_uint32)
    sig("ctl_core_take_notify", c_int, c_void_p, P(c_uint16))

    sig("ctl_host_size", c_size)
    sig("ctl_host_init", None, c_void_p, c_uint32)
    sig("ctl_host_boot", None, c_void_p)
    sig("ctl_host_take_output", c_size, c_void_p, c_char_p, c_size)
    for name in ("ctl_host_core", "ctl_host_store", "ctl_host_sim", "ctl_host_proto",
                 "ctl_host_midi"):
        sig(name, c_void_p, c_void_p)

    sig("ctl_host_counters", None, c_void_p, P(c_uint32))
    sig("ctl_host_tempo", c_void_p, c_void_p)
    sig("ctl_host_update", None, c_void_p, c_uint32)
    sig("ctl_tempo_midi", None, c_void_p, c_uint8, c_uint32)
    sig("ctl_tempo_tap", c_float, c_void_p, c_uint32)
    sig("ctl_tempo_beat_phase", c_float, c_void_p, c_uint32)
    sig("ctl_proto_feed", None, c_void_p, c_char_p, c_size)
    sig("ctl_proto_poll", None, c_void_p, c_size)
    sig("ctl_proto_meters", None, c_void_p)

    sig("ctl_midi_in", None, c_void_p, c_char_p, c_size, c_uint32)
    sig("ctl_midi_out", c_size, c_void_p, c_char_p, c_size)
    sig("ctl_midi_map_count", c_size)
    sig("ctl_midi_map_entry", P(CtlMidiMapEntry), c_size)
    sig("ctl_midi_cc_of", c_int, c_size)

    sig("ctl_preset_save", c_int, c_void_p, c_int, c_char_p, c_size, c_void_p)
    sig("ctl_preset_load", c_int, c_void_p, c_int, c_void_p)
    sig("ctl_preset_free_bytes", c_uint32, c_void_p)
    sig("ctl_preset_tick", None, c_void_p, c_void_p)
    sig("ctl_flash_sim_cut_after", None, c_void_p, ctypes.c_int64)
    sig("ctl_flash_sim_cut_next_erase", None, c_void_p)
    sig("ctl_flash_sim_power_on", None, c_void_p)
    sig("ctl_flash_sim_mem", P(c_uint8), c_void_p, c_uint32)

    # The panel input (batch 8d).
    for name in ("ctl_sizeof_pot", "ctl_sizeof_button", "ctl_sizeof_double", "ctl_sizeof_panel"):
        sig(name, c_size)
    sig("ctl_pot_coef", c_float, c_float)
    sig("ctl_pot_init", None, c_void_p, c_uint32, c_float)
    sig("ctl_pot_update", c_int, c_void_p, c_uint32, P(c_float))
    sig("ctl_pot_run", c_size, c_void_p, P(c_uint32), c_size, P(c_float), P(c_uint8))
    sig("ctl_pot_shape", c_float, P(CtlPotCal), c_int, c_float)
    sig("ctl_button_init", None, c_void_p)
    sig("ctl_button_update", c_uint32, c_void_p, c_int)
    sig("ctl_button_run", None, c_void_p, P(c_uint8), c_size, P(c_uint8))
    sig("ctl_double_init", None, c_void_p)
    sig("ctl_double_update", c_int, c_void_p, c_uint32)
    sig("ctl_led_hold", c_int, c_void_p, c_float, c_float, c_uint32, c_uint32)
    sig("ctl_panel_init", None, c_void_p, c_uint32)
    sig("ctl_panel_tick", None, c_void_p, c_void_p, P(c_uint32), c_uint32)
    sig("ctl_panel_leds", c_uint32, c_void_p, c_void_p, c_uint32)
    sig("ctl_panel_refused", c_uint32, c_void_p)
    return lib


def params(lib):
    """[(index, desc)] with the strings decoded."""
    out = []
    for i in range(lib.ctl_param_count()):
        d = lib.ctl_param_desc(i).contents
        out.append((i, d))
    return out


class Device:
    """A whole control stack with simulated flash: a device without hardware."""

    def __init__(self, lib, sector_bytes=128 * 1024):
        self.lib = lib
        self.buf = ctypes.create_string_buffer(lib.ctl_host_size())
        self.h = ctypes.cast(self.buf, c_void_p)
        lib.ctl_host_init(self.h, sector_bytes)

    @property
    def core(self):
        return self.lib.ctl_host_core(self.h)

    @property
    def store(self):
        return self.lib.ctl_host_store(self.h)

    @property
    def sim(self):
        return self.lib.ctl_host_sim(self.h)

    def reboot(self):
        self.lib.ctl_flash_sim_power_on(self.sim)
        self.lib.ctl_host_boot(self.h)

    def index(self, name):
        i = self.lib.ctl_param_find(name.encode(), len(name))
        assert i >= 0, name
        return i

    def get(self, name):
        return self.lib.ctl_core_get(self.core, self.index(name))

    def set(self, name, value, src=SRC_PC):
        return self.lib.ctl_core_set(self.core, self.index(name), value, src, None)

    def knob(self, name, x):
        return self.lib.ctl_core_knob(self.core, self.index(name), x)

    def time(self, ms):
        self.lib.ctl_core_set_time(self.core, ms)

    def output(self):
        out = ctypes.create_string_buffer(70000)
        n = self.lib.ctl_host_take_output(self.h, out, len(out))
        return out.raw[:n].decode("latin-1").splitlines()

    def send(self, text):
        """Sends bytes to the protocol and returns the lines that came back."""
        data = text.encode("latin-1") if isinstance(text, str) else text
        self.lib.ctl_proto_feed(self.lib.ctl_host_proto(self.h), data, len(data))
        return self.output()

    def cmd(self, line):
        """One command; returns (final line, data lines)."""
        lines = self.send(line + "\n")
        assert lines, line
        return lines[-1], lines[:-1]

    def poll(self, max_lines=100):
        self.lib.ctl_proto_poll(self.lib.ctl_host_proto(self.h), max_lines)
        return self.output()

    def midi(self, data, now_us=0):
        self.lib.ctl_midi_in(self.lib.ctl_host_midi(self.h), bytes(data), len(data), now_us)

    def midi_out(self):
        out = ctypes.create_string_buffer(512)
        n = self.lib.ctl_midi_out(self.lib.ctl_host_midi(self.h), out, len(out))
        return list(out.raw[:n])

    def update(self, now_us):
        self.lib.ctl_host_update(self.h, now_us & 0xFFFFFFFF)

    def tick(self, now_us, byte=0xF8):
        """A MIDI real-time byte at now_us, through the MIDI parser."""
        self.midi([byte], now_us & 0xFFFFFFFF)

    def counters(self):
        """clocks, starts, stops, continues, cc_in, cc_unmapped, sysex_skipped, taps"""
        out = (c_uint32 * 8)()
        self.lib.ctl_host_counters(self.h, out)
        keys = ("clocks", "starts", "stops", "continues", "cc_in", "cc_unmapped",
                "sysex_skipped", "taps")
        return dict(zip(keys, out))

    def save(self, slot, name=b"test"):
        return self.lib.ctl_preset_save(self.store, slot, name, len(name), self.core)

    def load(self, slot):
        return self.lib.ctl_preset_load(self.store, slot, self.core)


def _obj(size):
    buf = ctypes.create_string_buffer(size)
    return buf, ctypes.cast(buf, c_void_p)


class Pot:
    """One panel pot (ctl_pot.h)."""

    def __init__(self, lib, adc_bits=16, tau_ms=4.0):
        self.lib = lib
        self.buf, self.p = _obj(lib.ctl_sizeof_pot())
        lib.ctl_pot_init(self.p, adc_bits, tau_ms)

    def run(self, sums):
        """(travel after each reading, reported flags) for a stream of reading sums."""
        import numpy as np
        sums = np.ascontiguousarray(sums, dtype=np.uint32)
        travel = np.zeros(len(sums), dtype=np.float32)
        rep = np.zeros(len(sums), dtype=np.uint8)
        self.lib.ctl_pot_run(self.p, sums.ctypes.data_as(ctypes.POINTER(c_uint32)), len(sums),
                             travel.ctypes.data_as(ctypes.POINTER(c_float)),
                             rep.ctypes.data_as(ctypes.POINTER(c_uint8)))
        return travel, rep


class Button:
    """One debounced button (ctl_button.h)."""

    def __init__(self, lib):
        self.lib = lib
        self.buf, self.p = _obj(lib.ctl_sizeof_button())
        lib.ctl_button_init(self.p)

    def run(self, closed):
        import numpy as np
        closed = np.ascontiguousarray(closed, dtype=np.uint8)
        ev = np.zeros(len(closed), dtype=np.uint8)
        self.lib.ctl_button_run(self.p, closed.ctypes.data_as(ctypes.POINTER(c_uint8)),
                                len(closed), ev.ctypes.data_as(ctypes.POINTER(c_uint8)))
        return ev


class Panel:
    """The control panel (ctl_panel.h) on a Device's control core."""

    def __init__(self, dev, adc_bits=16):
        self.dev, self.lib = dev, dev.lib
        self.buf, self.p = _obj(self.lib.ctl_sizeof_panel())
        self.lib.ctl_panel_init(self.p, adc_bits)
        self.full = 16 * ((1 << adc_bits) - 1)
        self.travel = [0.5, 0.5, 0.5, 0.0, 0.0, 0.5, 0.5]
        self.closed = 0
        self.now_ms = 0

    def sums(self):
        return (c_uint32 * 7)(*[int(round(t * self.full)) for t in self.travel])

    def tick(self, ms=1, update_tempo=False):
        for _ in range(ms):
            self.lib.ctl_panel_tick(self.p, self.dev.core, self.sums(), self.closed)
            self.now_ms += 1
            if update_tempo:
                self.dev.update(self.now_ms * 1000)

    def press(self, button, hold_ms=50, gap_ms=50, update_tempo=False):
        self.closed |= 1 << button
        self.tick(hold_ms, update_tempo)
        self.closed &= ~(1 << button)
        self.tick(gap_ms, update_tempo)

    def leds(self, now_ms):
        return self.lib.ctl_panel_leds(self.p, self.dev.core, now_ms)

