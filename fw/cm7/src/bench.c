#include "bench.h"

#include "board.h"
#include "console.h"
#include "dsp/dsp_crc32.h"
#include "dsp/dsp_selftest.h"

#include <stdio.h>
#include <string.h>

enum { kRuns = 33 };

static uint32_t s_in[kDspSelftestFrames];
static uint32_t s_out[kDspSelftestFrames];

static const char *fmt_name(int fmt) { return fmt == kDspFmtQ31 ? "q31" : "f32"; }

static void sort(uint32_t *values, size_t count) {
    for (size_t i = 1; i < count; ++i) {
        const uint32_t value = values[i];
        size_t j = i;
        for (; j > 0 && values[j - 1] > value; --j) {
            values[j] = values[j - 1];
        }
        values[j] = value;
    }
}

static void run_case(size_t index) {
    uint32_t cycles[kRuns];
    dsp_selftest_input(index, s_in);
    for (size_t run = 0; run < kRuns; ++run) {
        const uint32_t start = board_cycles();
        dsp_selftest_run(index, s_in, s_out);
        cycles[run] = board_cycles() - start;
    }
    sort(cycles, kRuns);
    printf("bench %s fmt=%s frames=%d runs=%d min=%lu med=%lu max=%lu crc=%08lx\r\n",
           dsp_selftest_name(index), fmt_name(dsp_selftest_fmt(index)), (int)kDspSelftestFrames,
           (int)kRuns, (unsigned long)cycles[0], (unsigned long)cycles[kRuns / 2],
           (unsigned long)cycles[kRuns - 1],
           (unsigned long)dsp_crc32(0, s_out, sizeof(s_out)));
    console_flush();
}

void bench_run_all(void) {
    for (size_t index = 0; index < dsp_selftest_count(); ++index) {
        run_case(index);
    }
    printf("bench done\r\n");
}

void bench_list(void) {
    for (size_t index = 0; index < dsp_selftest_count(); ++index) {
        printf("case %s fmt=%s\r\n", dsp_selftest_name(index), fmt_name(dsp_selftest_fmt(index)));
    }
    printf("list done\r\n");
}

bool bench_dump_vector(const char *name) {
    for (size_t index = 0; index < dsp_selftest_count(); ++index) {
        if (strcmp(name, dsp_selftest_name(index)) != 0) {
            continue;
        }
        dsp_selftest_input(index, s_in);
        dsp_selftest_run(index, s_in, s_out);
        printf("vec %s %d\r\n", name, (int)kDspSelftestFrames);
        for (size_t i = 0; i < kDspSelftestFrames; ++i) {
            printf("%08lx%s", (unsigned long)s_out[i], (i % 8u) == 7u ? "\r\n" : " ");
            if ((i % 8u) == 7u) {
                console_flush(); /* Longer than the queue: send as we go. */
            }
        }
        printf("end\r\n");
        return true;
    }
    return false;
}
