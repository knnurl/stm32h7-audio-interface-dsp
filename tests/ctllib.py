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
