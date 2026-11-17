/* DSP audio interface, Cortex-M7. Batch 1: the skeleton; batch 8a: the control core.
 * It brings the board up at 400 MHz, runs the DSP library's self-test cases on request, and
 * answers the control protocol (docs/notes/control_protocol.md) on the console.
 *
 * Console (115200 8N1 on the ST-LINK virtual COM port). Board commands:
 *   info          the banner again
 *   cases         the self-test cases (was "list" before batch 8a)
 *   bench         run every case: cycles and output checksum
 *   vec <name>    dump one case's output
 *   fault         the last recorded fault, if any
 *   ptime         time one write of the power-on record to flash
 * Every other line goes to the control protocol: hello, list, get, set, mode, meters, preset,
 * src, tempo, stat.
 */
#include "bench.h"
#include "board.h"
#include "console.h"
#include "fault.h"
#include "flash_store.h"

#include "ctl/ctl_core.h"
#include "ctl/ctl_preset.h"
#include "ctl/ctl_proto.h"

#include <stdio.h>
#include <string.h>

#define FW_VERSION "0.2.0"
#define METERS_PERIOD_MS 33u /* About 30 Hz. */

static CtlCore s_core;
static CtlPresetStore s_presets;
static CtlProto s_proto;

static void print_info(void) {
    const uint32_t idcode = DBGMCU->IDCODE;
    printf("dsp-interface fw %s cm7\r\n", FW_VERSION);
    printf("device id=0x%03lx rev=0x%04lx\r\n", (unsigned long)(idcode & 0xFFFu),
           (unsigned long)(idcode >> 16));
    printf("clock sysclk=%lu hclk=%lu pclk1=%lu measured_cycles_per_ms=%lu\r\n",
           (unsigned long)HAL_RCC_GetSysClockFreq(), (unsigned long)HAL_RCC_GetHCLKFreq(),
           (unsigned long)HAL_RCC_GetPCLK1Freq(),
           (unsigned long)board_measure_cycles_per_ms(20));
    printf("supply direct-smps vos=1 cm4_parked=%d\r\n", board_cm4_parked() ? 1 : 0);
    printf("console dropped=%lu\r\n", (unsigned long)console_dropped());
    printf("info done\r\n");
}

/* The protocol's lines go out whole: wait for room rather than drop (main loop only). */
static void proto_write(void *ctx, const char *line, size_t len) {
    (void)ctx;
    fflush(stdout);
    if (console_free() < len + 2u) {
        console_flush();
    }
    console_write(line, len);
    console_write("\r\n", 2u);
}

static void time_preset_write(void) {
    const uint32_t start = board_cycles();
    const int r = ctl_preset_save(&s_presets, CTL_PRESET_POWER_ON, "power-on", 8u, &s_core);
    const uint32_t cycles = board_cycles() - start;
    printf("ptime result=%d cycles=%lu us=%lu compactions=%lu free=%lu\r\n", r,
           (unsigned long)cycles, (unsigned long)(cycles / 400u),
           (unsigned long)s_presets.compactions,
           (unsigned long)ctl_preset_free_bytes(&s_presets));
}

static void handle_line(const char *line) {
    if (strcmp(line, "info") == 0) {
        print_info();
    } else if (strcmp(line, "cases") == 0) {
        bench_list();
    } else if (strcmp(line, "bench") == 0) {
        bench_run_all();
    } else if (strncmp(line, "vec ", 4) == 0) {
        if (!bench_dump_vector(line + 4)) {
            printf("error no case named %s\r\n", line + 4);
        }
    } else if (strcmp(line, "fault") == 0) {
        char text[260];
        fault_describe(text, sizeof(text));
        printf("%s\r\n", text);
    } else if (strcmp(line, "ptime") == 0) {
        time_preset_write();
    } else {
        ctl_proto_line(&s_proto, line, strlen(line));
    }
}

static void control_init(void) {
    static CtlFlashOps flash;
    flash_store_ops(&flash);
    ctl_core_init(&s_core);
    ctl_core_set_time(&s_core, HAL_GetTick());
    (void)ctl_preset_mount(&s_presets, &flash);
    (void)ctl_preset_restore(&s_presets, &s_core);
    ctl_core_sync_audio(&s_core); /* Nothing drains it until batch 2; it cannot overflow. */
    const uint32_t unit_id = HAL_GetUIDw0() ^ HAL_GetUIDw1() ^ HAL_GetUIDw2();
    ctl_proto_init(&s_proto, &s_core, &s_presets, proto_write, NULL, FW_VERSION, unit_id);
}

int main(void) {
    board_init();
    fault_report_boot();
    print_info();
    control_init();

    uint32_t last_blink_ms = 0;
    uint32_t last_meters_ms = 0;
    char line[CTL_PROTO_INPUT_MAX + 1];
    for (;;) {
        const uint32_t now = HAL_GetTick();
        ctl_core_set_time(&s_core, now);
        if (console_read_line(line, sizeof(line))) {
            handle_line(line);
        }
        ctl_proto_poll(&s_proto, 4u);
        ctl_preset_tick(&s_presets, &s_core);
        if (now - last_meters_ms >= METERS_PERIOD_MS) {
            last_meters_ms = now;
            ctl_proto_meters(&s_proto);
        }
        if (now - last_blink_ms >= 500u) {
            last_blink_ms = now;
            board_led_toggle(kLedGreen);
        }
    }
}
