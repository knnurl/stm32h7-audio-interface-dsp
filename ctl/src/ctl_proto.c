#include "ctl/ctl_proto.h"

#include <string.h>

#define MAX_TOKENS 4

typedef struct {
    const char *s;
    size_t len;
} Token;

static int token_is(const Token *t, const char *word) {
    const size_t n = strlen(word);
    return t->len == n && memcmp(t->s, word, n) == 0;
}

static int is_space(char c) { return c == ' ' || c == '\t'; }

/* Splits into up to MAX_TOKENS tokens; `rest` is the text from the last token on (for names). */
static size_t tokenise(const char *line, size_t len, Token *t, size_t max, const char **rest,
                       size_t *rest_len) {
    size_t n = 0, i = 0;
    *rest = line + len;
    *rest_len = 0;
    while (i < len && n < max) {
        while (i < len && is_space(line[i])) {
            ++i;
        }
        if (i == len) {
            break;
        }
        const size_t start = i;
        while (i < len && !is_space(line[i])) {
            ++i;
        }
        t[n].s = line + start;
        t[n].len = i - start;
        if (n + 1u == max) {
            *rest = line + start;
            *rest_len = len - start;
            while (*rest_len > 0u && is_space((*rest)[*rest_len - 1u])) {
                --*rest_len;
            }
        }
        ++n;
    }
    /* Anything left beyond the last token counts as one more token (too many arguments). */
    while (i < len && is_space(line[i])) {
        ++i;
    }
    if (i < len && n == max) {
        ++n;
    }
    return n;
}

static void send(CtlProto *p) {
    p->write(p->write_ctx, p->out.text, p->out.len);
    ctl_line_clear(&p->out);
}

static void reply_err(CtlProto *p, CtlResult code, const char *reason) {
    ++p->errors;
    ctl_line_clear(&p->out);
    ctl_line_str(&p->out, "err ");
    ctl_line_uint(&p->out, (uint32_t)code);
    ctl_line_char(&p->out, ' ');
    ctl_line_str(&p->out, reason);
    send(p);
}

static const char *result_reason(CtlResult r) {
    switch (r) {
    case kCtlErrUnknownParam:
        return "unknown parameter";
    case kCtlErrBadValue:
        return "bad value";
    case kCtlErrKnobWins:
        return "knob wins: set the mode to pc first";
    case kCtlErrReadOnly:
        return "read-only";
    case kCtlErrNotKnob:
        return "parameter has no knob";
    case kCtlErrBudget:
        return "budget: the effect slot and strip saturation cannot run together";
    default:
        return "failed";
    }
}

static int32_t find_param(const Token *t) { return ctl_param_find(t->s, t->len); }

static void begin_ok(CtlProto *p, const char *what) {
    ctl_line_clear(&p->out);
    ctl_line_str(&p->out, "ok ");
    ctl_line_str(&p->out, what);
}

static void name_value(CtlProto *p, size_t index) {
    ctl_line_str(&p->out, ctl_param_desc(index)->name);
    ctl_line_char(&p->out, ' ');
    ctl_line_float(&p->out, ctl_core_get(p->core, index));
}

static void cmd_hello(CtlProto *p) {
    begin_ok(p, "hello proto=");
    ctl_line_uint(&p->out, CTL_PROTO_VERSION);
    ctl_line_str(&p->out, " fw=");
    ctl_line_str(&p->out, p->fw_version);
    ctl_line_str(&p->out, " unit=");
    ctl_line_hex(&p->out, p->unit_id);
    ctl_line_str(&p->out, " params=");
    ctl_line_uint(&p->out, (uint32_t)ctl_param_count());
    send(p);
}

static void cmd_list(CtlProto *p) {
    static const char *const kCurve[] = {"lin", "log", "vol", "step"};
    static const char kFlag[] = "kbpsr";
    const size_t n = ctl_param_count();
    for (size_t i = 0; i < n; ++i) {
        const CtlParamDesc *d = ctl_param_desc(i);
        ctl_line_clear(&p->out);
        ctl_line_str(&p->out, "= ");
        ctl_line_uint(&p->out, d->id);
        ctl_line_char(&p->out, ' ');
        ctl_line_str(&p->out, d->name);
        ctl_line_char(&p->out, ' ');
        ctl_line_str(&p->out, d->unit[0] != '\0' ? d->unit : "-");
        ctl_line_char(&p->out, ' ');
        ctl_line_float(&p->out, d->min);
        ctl_line_char(&p->out, ' ');
        ctl_line_float(&p->out, d->max);
        ctl_line_char(&p->out, ' ');
        ctl_line_float(&p->out, d->def);
        ctl_line_char(&p->out, ' ');
        ctl_line_str(&p->out, d->curve <= kCtlCurveStep ? kCurve[d->curve] : "?");
        ctl_line_char(&p->out, ' ');
        if (d->flags == 0u) {
            ctl_line_char(&p->out, '-');
        }
        for (int b = 0; b < 5; ++b) {
            if ((d->flags & (1u << b)) != 0u) {
                ctl_line_char(&p->out, kFlag[b]);
            }
        }
        ctl_line_char(&p->out, ' ');
        ctl_line_str(&p->out, d->label);
        send(p);
    }
    begin_ok(p, "list ");
    ctl_line_uint(&p->out, (uint32_t)n);
    send(p);
}

static void cmd_get(CtlProto *p, const Token *t, size_t n) {
    if (n != 2u) {
        reply_err(p, kCtlErrSyntax, "usage: get <name>");
        return;
    }
    const int32_t i = find_param(&t[1]);
    if (i < 0) {
        reply_err(p, kCtlErrUnknownParam, "unknown parameter");
        return;
    }
    begin_ok(p, "");
    name_value(p, (size_t)i);
    send(p);
}

static void cmd_set(CtlProto *p, const Token *t, size_t n) {
    if (n != 3u) {
        reply_err(p, kCtlErrSyntax, "usage: set <name> <value>");
        return;
    }
    const int32_t i = find_param(&t[1]);
    float v;
    if (i < 0) {
        reply_err(p, kCtlErrUnknownParam, "unknown parameter");
        return;
    }
    if (ctl_parse_float(t[2].s, t[2].len, &v) != 0) {
        reply_err(p, kCtlErrBadValue, "bad value");
        return;
    }
    const CtlResult r = ctl_core_set(p->core, (size_t)i, v, kCtlSrcPc, NULL);
    if (r != kCtlOk) {
        reply_err(p, r, result_reason(r));
        return;
    }
    begin_ok(p, "");
    name_value(p, (size_t)i);
    send(p);
}

static void cmd_mode(CtlProto *p, const Token *t, size_t n) {
    if (n != 2u && n != 3u) {
        reply_err(p, kCtlErrSyntax, "usage: mode <name> [knob|pc]");
        return;
    }
    const int32_t i = find_param(&t[1]);
    if (i < 0) {
        reply_err(p, kCtlErrUnknownParam, "unknown parameter");
        return;
    }
    const int32_t m = ctl_param_mode_index((size_t)i);
    if (m < 0) {
        reply_err(p, kCtlErrNotKnob, "parameter has no knob");
        return;
    }
    if (n == 3u) {
        float mode;
        if (token_is(&t[2], "knob")) {
            mode = 0.0f;
        } else if (token_is(&t[2], "pc")) {
            mode = 1.0f;
        } else {
            reply_err(p, kCtlErrBadValue, "mode is knob or pc");
            return;
        }
        (void)ctl_core_set(p->core, (size_t)m, mode, kCtlSrcPc, NULL);
    }
    begin_ok(p, "mode ");
    ctl_line_str(&p->out, ctl_param_desc((size_t)i)->name);
    ctl_line_str(&p->out, ctl_core_mode(p->core, (size_t)i) == 0 ? " knob" : " pc");
    ctl_line_str(&p->out, " attached=");
    ctl_line_uint(&p->out, (uint32_t)ctl_core_knob_attached(p->core, (size_t)i));
    send(p);
}

static void cmd_meters(CtlProto *p, const Token *t, size_t n) {
    if (n == 2u && token_is(&t[1], "on")) {
        p->meters_on = 1u;
    } else if (n == 2u && token_is(&t[1], "off")) {
        p->meters_on = 0u;
    } else if (n != 1u) {
        reply_err(p, kCtlErrSyntax, "usage: meters on|off");
        return;
    }
    begin_ok(p, p->meters_on ? "meters on" : "meters off");
    send(p);
}

/* Slot numbers in the protocol are 1 to 8. */
static int parse_slot(const Token *t) {
    uint32_t v;
    if (ctl_parse_uint(t->s, t->len, &v) != 0 || v < 1u || v > CTL_PRESET_SLOTS) {
        return -1;
    }
    return (int)v - 1;
}

static void cmd_preset(CtlProto *p, const Token *t, size_t n, const char *rest, size_t rest_len) {
    if (p->presets == NULL) {
        reply_err(p, kCtlErrPreset, "no preset store");
        return;
    }
    if (n == 2u && token_is(&t[1], "list")) {
        uint32_t count = 0;
        for (int slot = 0; slot < CTL_PRESET_SLOTS; ++slot) {
            char name[CTL_PRESET_NAME_LEN + 1];
            uint32_t seq;
            if (ctl_preset_info(p->presets, slot, name, &seq) != 0) {
                continue;
            }
            ++count;
            ctl_line_clear(&p->out);
            ctl_line_str(&p->out, "= ");
            ctl_line_uint(&p->out, (uint32_t)slot + 1u);
            ctl_line_str(&p->out, " seq=");
            ctl_line_uint(&p->out, seq);
            ctl_line_char(&p->out, ' ');
            ctl_line_str(&p->out, name);
            send(p);
        }
        begin_ok(p, "preset list ");
        ctl_line_uint(&p->out, count);
        send(p);
        return;
    }
    if (n < 3u) {
        reply_err(p, kCtlErrSyntax, "usage: preset save|load|name <1-8> [name], preset list");
        return;
    }
    const int slot = parse_slot(&t[2]);
    if (slot < 0) {
        reply_err(p, kCtlErrBadValue, "slot is 1 to 8");
        return;
    }
    int r;
    if (token_is(&t[1], "save")) {
        if (n == 4u || n == 5u) {
            r = ctl_preset_save(p->presets, slot, rest, rest_len, p->core);
        } else {
            char name[] = "preset 0";
            name[7] = (char)('1' + slot);
            r = ctl_preset_save(p->presets, slot, name, sizeof(name) - 1u, p->core);
        }
    } else if (token_is(&t[1], "load") && n == 3u) {
        const uint32_t refused_before = p->core->refused;
        r = ctl_preset_load(p->presets, slot, p->core);
        if (r == 0) {
            begin_ok(p, "preset load ");
            ctl_line_uint(&p->out, (uint32_t)slot + 1u);
            ctl_line_str(&p->out, " refused=");
            ctl_line_uint(&p->out, p->core->refused - refused_before);
            send(p);
            return;
        }
    } else if (token_is(&t[1], "name") && (n == 4u || n == 5u)) {
        r = ctl_preset_rename(p->presets, slot, rest, rest_len);
    } else {
        reply_err(p, kCtlErrSyntax, "usage: preset save|load|name <1-8> [name], preset list");
        return;
    }
    if (r != 0) {
        reply_err(p, kCtlErrPreset, "preset store failed or slot empty");
        return;
    }
    begin_ok(p, "preset ");
    ctl_line_mem(&p->out, t[1].s, t[1].len);
    ctl_line_char(&p->out, ' ');
    ctl_line_uint(&p->out, (uint32_t)slot + 1u);
    send(p);
}

static void cmd_src(CtlProto *p, const Token *t, size_t n) {
    const int32_t i = ctl_param_find("record_source", 13u);
    if (n == 2u && (token_is(&t[1], "inputs") || token_is(&t[1], "mix"))) {
        (void)ctl_core_set(p->core, (size_t)i, token_is(&t[1], "mix") ? 1.0f : 0.0f, kCtlSrcPc,
                           NULL);
    } else if (n != 1u) {
        reply_err(p, kCtlErrSyntax, "usage: src inputs|mix");
        return;
    }
    begin_ok(p, ctl_core_get(p->core, (size_t)i) >= 0.5f ? "src mix" : "src inputs");
    send(p);
}

static void cmd_tempo(CtlProto *p, const Token *t, size_t n) {
    const int32_t i = ctl_param_find("tempo_bpm", 9u);
    if (n == 2u) {
        float bpm;
        if (ctl_parse_float(t[1].s, t[1].len, &bpm) != 0) {
            reply_err(p, kCtlErrBadValue, "bad value");
            return;
        }
        (void)ctl_core_set(p->core, (size_t)i, bpm, kCtlSrcPc, NULL);
    } else if (n != 1u) {
        reply_err(p, kCtlErrSyntax, "usage: tempo [bpm]");
        return;
    }
    begin_ok(p, "tempo ");
    if (p->tempo != NULL && p->tempo->source == kCtlTempoMidi) {
        ctl_line_float(&p->out, p->tempo->bpm);
        ctl_line_str(&p->out, " source=midi stored=");
    }
    ctl_line_float(&p->out, ctl_core_get(p->core, (size_t)i));
    if (p->tempo == NULL || p->tempo->source != kCtlTempoMidi) {
        ctl_line_str(&p->out, " source=stored");
    }
    send(p);
}

static void stat_field(CtlProto *p, const char *name, uint32_t v) {
    ctl_line_char(&p->out, ' ');
    ctl_line_str(&p->out, name);
    ctl_line_char(&p->out, '=');
    ctl_line_uint(&p->out, v);
}

static void cmd_stat(CtlProto *p) {
    begin_ok(p, "stat");
    stat_field(p, "lines", p->lines);
    stat_field(p, "errors", p->errors);
    stat_field(p, "refused", p->core->refused);
    stat_field(p, "to_audio", p->core->to_audio.pushes);
    stat_field(p, "coalesced", p->core->to_audio.coalesced);
    stat_field(p, "waiting", ctl_queue_waiting(&p->core->to_audio));
    if (p->presets != NULL) {
        stat_field(p, "preset_writes", p->presets->writes);
        stat_field(p, "compactions", p->presets->compactions);
        stat_field(p, "flash_errors", p->presets->errors);
        stat_field(p, "flash_free", ctl_preset_free_bytes(p->presets));
    }
    send(p);
}

void ctl_proto_line(CtlProto *p, const char *line, size_t len) {
    Token t[MAX_TOKENS];
    const char *rest;
    size_t rest_len;
    const size_t n = tokenise(line, len, t, MAX_TOKENS, &rest, &rest_len);
    if (n == 0u) {
        return; /* Blank line: no reply. */
    }
    ++p->lines;
    if (token_is(&t[0], "hello") && n == 1u) {
        cmd_hello(p);
    } else if (token_is(&t[0], "list") && n == 1u) {
        cmd_list(p);
    } else if (token_is(&t[0], "get")) {
        cmd_get(p, t, n);
    } else if (token_is(&t[0], "set")) {
        cmd_set(p, t, n);
    } else if (token_is(&t[0], "mode")) {
        cmd_mode(p, t, n);
    } else if (token_is(&t[0], "meters")) {
        cmd_meters(p, t, n);
    } else if (token_is(&t[0], "preset")) {
        cmd_preset(p, t, n, rest, rest_len);
    } else if (token_is(&t[0], "src")) {
        cmd_src(p, t, n);
    } else if (token_is(&t[0], "tempo")) {
        cmd_tempo(p, t, n);
    } else if (token_is(&t[0], "stat") && n == 1u) {
        cmd_stat(p);
    } else {
        reply_err(p, kCtlErrUnknownCommand, "unknown command");
    }
}

void ctl_proto_feed(CtlProto *p, const char *bytes, size_t n) {
    for (size_t i = 0; i < n; ++i) {
        const char c = bytes[i];
        if (c == '\r' || c == '\n') {
            if (p->input_overflow) {
                ++p->lines;
                reply_err(p, kCtlErrTooLong, "line too long");
            } else if (p->input_len > 0u) {
                ctl_proto_line(p, p->input, p->input_len);
            }
            p->input_len = 0;
            p->input_overflow = 0;
        } else if (p->input_len < CTL_PROTO_INPUT_MAX) {
            p->input[p->input_len++] = c;
        } else {
            p->input_overflow = 1;
        }
    }
}

void ctl_proto_poll(CtlProto *p, size_t max_lines) {
    uint16_t index;
    for (size_t k = 0; k < max_lines && ctl_core_take_notify(p->core, &index); ++k) {
        ctl_line_clear(&p->out);
        ctl_line_str(&p->out, "# set ");
        name_value(p, index);
        send(p);
    }
}

void ctl_proto_meters(CtlProto *p) {
    if (!p->meters_on) {
        return;
    }
    ctl_line_clear(&p->out);
    ctl_line_str(&p->out, "# meters");
    const size_t n = ctl_param_count();
    for (size_t i = 0; i < n; ++i) {
        const CtlParamDesc *d = ctl_param_desc(i);
        if ((d->flags & kCtlFlagReadOnly) == 0u) {
            continue;
        }
        ctl_line_char(&p->out, ' ');
        ctl_line_str(&p->out, d->name);
        ctl_line_char(&p->out, '=');
        ctl_line_float(&p->out, ctl_core_get(p->core, i));
    }
    send(p);
}

void ctl_proto_init(CtlProto *p, CtlCore *core, CtlPresetStore *presets, CtlWriteFn write,
                    void *write_ctx, const char *fw_version, uint32_t unit_id) {
    memset(p, 0, sizeof(*p));
    p->core = core;
    p->presets = presets;
    p->write = write;
    p->write_ctx = write_ctx;
    p->fw_version = fw_version;
    p->unit_id = unit_id;
    ctl_line_clear(&p->out);
}
