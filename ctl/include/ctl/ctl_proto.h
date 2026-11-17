/* The control protocol, version 1 (docs/notes/control_protocol.md is the specification).
 *
 * Line-based text, one command per line. Every command ends with exactly one line starting
 * "ok" or "err <code> <reason>"; `list` and `preset list` send data lines starting "= " before
 * it. Lines the device sends unasked (changes from the knobs, MIDI or presets; meters) start
 * with "#". Transport-agnostic: the transport hands bytes to ctl_proto_feed (or whole lines to
 * ctl_proto_line) and gets lines back through `write`, without line endings.
 */
#ifndef CTL_PROTO_H
#define CTL_PROTO_H

#include "ctl/ctl_core.h"
#include "ctl/ctl_preset.h"
#include "ctl/ctl_text.h"

#include <stddef.h>
#include <stdint.h>

#define CTL_PROTO_VERSION 1u
#define CTL_PROTO_INPUT_MAX 128u

typedef void (*CtlWriteFn)(void *ctx, const char *line, size_t len);

typedef struct {
    CtlCore *core;
    CtlPresetStore *presets; /* May be NULL: preset commands then answer err 7. */
    CtlWriteFn write;
    void *write_ctx;
    const char *fw_version;
    uint32_t unit_id;
    uint8_t meters_on;
    /* Input line being assembled by ctl_proto_feed. */
    char input[CTL_PROTO_INPUT_MAX + 1];
    size_t input_len;
    uint8_t input_overflow;
    CtlLine out;
    uint32_t lines;
    uint32_t errors;
} CtlProto;

void ctl_proto_init(CtlProto *p, CtlCore *core, CtlPresetStore *presets, CtlWriteFn write,
                    void *write_ctx, const char *fw_version, uint32_t unit_id);
/* Bytes from the transport, any split. CR, LF or CR LF end a line. A line longer than
 * CTL_PROTO_INPUT_MAX is answered with err 8 when it ends. */
void ctl_proto_feed(CtlProto *p, const char *bytes, size_t n);
/* One complete command line (no line ending). */
void ctl_proto_line(CtlProto *p, const char *line, size_t len);
/* Sends up to `max_lines` "# set <name> <value>" lines for changes the PC has not seen. */
void ctl_proto_poll(CtlProto *p, size_t max_lines);
/* Sends one "# meters name=value ..." line when meters are on (the caller paces it, 30 Hz). */
void ctl_proto_meters(CtlProto *p);

#endif
