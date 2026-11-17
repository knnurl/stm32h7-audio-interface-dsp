/* Fuzz driver for the protocol and MIDI parsers, built with the address sanitiser on MSVC
 * (ctl/CMakeLists.txt). Feeds deterministic random bytes, and random lines made of real command
 * words, through ctl_proto_feed and ctl_midi_in. Any out-of-bounds access stops it with a report;
 * a clean run prints "fuzz ok" and the counts. Run by tests/unit/test_ctl_proto.py.
 *
 * Usage: ctl_fuzz [iterations] [seed]
 */
#include "ctl/ctl_host.h"

#include <stdio.h>
#include <stdlib.h>
#include <string.h>

static uint32_t s_rng;

static uint32_t next(void) {
    s_rng ^= s_rng << 13;
    s_rng ^= s_rng >> 17;
    s_rng ^= s_rng << 5;
    return s_rng;
}

static const char *const kWords[] = {
    "hello", "list", "get", "set", "mode", "meters", "preset", "src", "tempo", "stat",
    "save", "load", "name", "on", "off", "knob", "pc", "inputs", "mix", "1", "8", "9", "0",
    "-1", "tone_bass_db", "monitor_volume_db", "fx_select", "in1_peak_db", "mode_blend",
    "1e40", "-1e-40", "nan", "3.5", ".", "-", "e5", "12e", "999999999999", "\t", "  "};

int main(int argc, char **argv) {
    const long iterations = argc > 1 ? strtol(argv[1], NULL, 10) : 200000L;
    s_rng = argc > 2 ? (uint32_t)strtoul(argv[2], NULL, 10) : 12345u;
    if (s_rng == 0u) {
        s_rng = 1u;
    }
    CtlHost *h = (CtlHost *)malloc(ctl_host_size());
    if (h == NULL) {
        return 2;
    }
    ctl_host_init(h, 8192u);
    const size_t blend = (size_t)ctl_param_find("blend", 5u);
    char sink[4096];
    uint8_t bytes[300];
    unsigned long fed = 0;
    for (long it = 0; it < iterations; ++it) {
        const uint32_t kind = next() % 4u;
        size_t n = 0;
        if (kind == 0u) { /* Raw bytes. */
            n = 1u + next() % sizeof(bytes);
            for (size_t i = 0; i < n; ++i) {
                bytes[i] = (uint8_t)next();
            }
            ctl_proto_feed(ctl_host_proto(h), (const char *)bytes, n);
        } else if (kind == 1u) { /* Lines of real words, sometimes too long. */
            const size_t words = 1u + next() % 8u;
            for (size_t w = 0; w < words && n < sizeof(bytes) - 40u; ++w) {
                const char *word = kWords[next() % (sizeof(kWords) / sizeof(kWords[0]))];
                const size_t len = strlen(word);
                memcpy(bytes + n, word, len);
                n += len;
                bytes[n++] = (next() % 8u) == 0u ? (uint8_t)next() : (uint8_t)' ';
            }
            bytes[n++] = (next() % 2u) ? '\n' : '\r';
            ctl_proto_feed(ctl_host_proto(h), (const char *)bytes, n);
        } else { /* MIDI. */
            n = 1u + next() % 64u;
            for (size_t i = 0; i < n; ++i) {
                bytes[i] = (uint8_t)next();
            }
            ctl_midi_in(ctl_host_midi(h), bytes, n, (uint32_t)it);
            uint8_t out[96];
            (void)ctl_midi_out(ctl_host_midi(h), out, sizeof(out));
        }
        fed += (unsigned long)n;
        if ((next() % 16u) == 0u) {
            ctl_core_knob(ctl_host_core(h), blend, (float)(next() % 1001u) / 1000.0f);
            ctl_proto_poll(ctl_host_proto(h), 8u);
        }
        while (ctl_host_take_output(h, sink, sizeof(sink)) > 0u) {
        }
    }
    printf("fuzz ok iterations=%ld bytes=%lu lines=%lu errors=%lu\n", iterations, fed,
           (unsigned long)ctl_host_proto(h)->lines, (unsigned long)ctl_host_proto(h)->errors);
    free(h);
    return 0;
}
