/* DSP audio interface, Cortex-M7. Batch 1: the skeleton. It brings the board up at 400 MHz,
 * reports what it finds, and runs the DSP library's self-test cases on request.
 *
 * Console commands (115200 8N1 on the ST-LINK virtual COM port):
 *   info          the banner again
 *   list          the self-test cases
 *   bench         run every case: cycles and output checksum
 *   vec <name>    dump one case's output
 *   fault         the last recorded fault, if any
 */
#include "bench.h"
#include "board.h"
#include "console.h"
#include "fault.h"

#include <stdio.h>
#include <string.h>

#define FW_VERSION "0.1.0"

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

static void handle_line(const char *line) {
    if (strcmp(line, "info") == 0) {
        print_info();
    } else if (strcmp(line, "list") == 0) {
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
    } else {
        printf("error unknown command: %s (info, list, bench, vec <name>, fault)\r\n", line);
    }
}

int main(void) {
    board_init();
    fault_report_boot();
    print_info();

    uint32_t last_blink_ms = 0;
    char line[96];
    for (;;) {
        if (console_read_line(line, sizeof(line))) {
            handle_line(line);
        }
        if (HAL_GetTick() - last_blink_ms >= 500u) {
            last_blink_ms = HAL_GetTick();
            board_led_toggle(kLedGreen);
        }
    }
}
