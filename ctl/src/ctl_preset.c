#include "ctl/ctl_preset.h"

#include "dsp/dsp_crc32.h"

#include <math.h>
#include <string.h>

/* Little-endian fields, written byte by byte so the layout does not depend on the compiler. */
#define SECTOR_MAGIC 0x54455350u /* "PSET" */
#define RECORD_MAGIC 0xC7A1u
#define FORMAT_VERSION 1u
#define ENTRY_BYTES 8u
#define FIRST_RECORD CTL_FLASH_WORD

static void put16(uint8_t *p, uint32_t v) {
    p[0] = (uint8_t)v;
    p[1] = (uint8_t)(v >> 8);
}
static void put32(uint8_t *p, uint32_t v) {
    put16(p, v & 0xFFFFu);
    put16(p + 2, v >> 16);
}
static uint32_t get16(const uint8_t *p) { return (uint32_t)p[0] | ((uint32_t)p[1] << 8); }
static uint32_t get32(const uint8_t *p) { return get16(p) | (get16(p + 2) << 16); }

static uint32_t round_word(uint32_t n) {
    return (n + CTL_FLASH_WORD - 1u) / CTL_FLASH_WORD * CTL_FLASH_WORD;
}

static uint8_t slot_mask(int slot) {
    return slot == CTL_PRESET_POWER_ON ? (uint8_t)(kCtlFlagPreset | kCtlFlagSetting)
                                       : (uint8_t)kCtlFlagPreset;
}

static uint32_t count_params(uint8_t mask) {
    uint32_t n = 0;
    for (size_t i = 0; i < ctl_param_count(); ++i) {
        if ((ctl_param_desc(i)->flags & mask) != 0u) {
            ++n;
        }
    }
    return n;
}

static uint32_t record_bytes(uint32_t count) {
    return round_word(CTL_PRESET_HEADER_BYTES + CTL_PRESET_NAME_LEN + ENTRY_BYTES * count);
}

/* ---- Records ---------------------------------------------------------------------------- */

typedef struct {
    uint32_t slot;
    uint32_t seq;
    uint32_t payload_len;
    uint32_t count;
    uint32_t total; /* Bytes the record occupies, rounded to a flash word. */
    int crc_ok;
} RecordInfo;

enum { kScanRecord = 0, kScanEnd = 1, kScanGarbage = 2 };

/* Reads the record at `off` into store->buf. */
static int read_record(CtlPresetStore *s, uint32_t off, RecordInfo *info) {
    const uint32_t size = s->flash.sector_bytes;
    uint8_t *h = s->buf;
    if (off + CTL_PRESET_HEADER_BYTES > size ||
        s->flash.read(s->flash.ctx, (uint32_t)s->active, off, h, CTL_PRESET_HEADER_BYTES) != 0) {
        return kScanEnd;
    }
    int blank = 1;
    for (uint32_t i = 0; i < CTL_PRESET_HEADER_BYTES; ++i) {
        blank &= h[i] == 0xFFu;
    }
    if (blank) {
        return kScanEnd;
    }
    info->slot = h[2];
    info->seq = get32(h + 4);
    info->payload_len = get16(h + 8);
    info->count = get16(h + 10);
    if (get16(h) != RECORD_MAGIC || h[3] != FORMAT_VERSION || info->slot > CTL_PRESET_POWER_ON ||
        info->count > CTL_MAX_PARAMS ||
        info->payload_len != CTL_PRESET_NAME_LEN + ENTRY_BYTES * info->count) {
        return kScanGarbage;
    }
    info->total = round_word(CTL_PRESET_HEADER_BYTES + info->payload_len);
    if (off + info->total > size ||
        s->flash.read(s->flash.ctx, (uint32_t)s->active, off + CTL_PRESET_HEADER_BYTES,
                      h + CTL_PRESET_HEADER_BYTES, info->payload_len) != 0) {
        return kScanGarbage;
    }
    uint32_t crc = dsp_crc32(0u, h, 12u);
    crc = dsp_crc32(crc, h + CTL_PRESET_HEADER_BYTES, info->payload_len);
    info->crc_ok = crc == get32(h + 12);
    return kScanRecord;
}

/* Offset of the slot's latest record with a good CRC (left in buf), or 0. */
static uint32_t find_latest(CtlPresetStore *s, int slot, RecordInfo *best) {
    if (s->active < 0) {
        return 0;
    }
    uint32_t best_off = 0;
    RecordInfo info;
    for (uint32_t off = FIRST_RECORD; read_record(s, off, &info) == kScanRecord;
         off += info.total) {
        if (info.crc_ok && info.slot == (uint32_t)slot && (best_off == 0 || info.seq > best->seq)) {
            best_off = off;
            *best = info;
        }
    }
    if (best_off != 0 && read_record(s, best_off, best) != kScanRecord) {
        return 0;
    }
    return best_off;
}

/* ---- Sectors ---------------------------------------------------------------------------- */

static int read_header(CtlPresetStore *s, uint32_t sector, uint32_t *generation) {
    uint8_t h[16];
    if (s->flash.read(s->flash.ctx, sector, 0, h, sizeof(h)) != 0) {
        return 0;
    }
    if (get32(h) != SECTOR_MAGIC || get32(h + 8) != FORMAT_VERSION ||
        dsp_crc32(0u, h, 12u) != get32(h + 12)) {
        return 0;
    }
    *generation = get32(h + 4);
    return 1;
}

static int write_header(CtlPresetStore *s, uint32_t sector, uint32_t generation) {
    uint8_t w[CTL_FLASH_WORD];
    memset(w, 0xFF, sizeof(w));
    put32(w, SECTOR_MAGIC);
    put32(w + 4, generation);
    put32(w + 8, FORMAT_VERSION);
    put32(w + 12, dsp_crc32(0u, w, 12u));
    return s->flash.program(s->flash.ctx, sector, 0, w, sizeof(w));
}

static void scan(CtlPresetStore *s) {
    s->next_seq = 1;
    s->needs_compact = 0;
    uint32_t off = FIRST_RECORD;
    RecordInfo info;
    for (;;) {
        const int r = read_record(s, off, &info);
        if (r == kScanEnd) {
            break;
        }
        if (r == kScanGarbage) {
            s->needs_compact = 1; /* Its length cannot be trusted: nothing after it is usable. */
            break;
        }
        if (info.crc_ok && info.seq >= s->next_seq) {
            s->next_seq = info.seq + 1u;
        }
        off += info.total;
    }
    s->free_offset = off;
}

int ctl_preset_mount(CtlPresetStore *store, const CtlFlashOps *flash) {
    memset(store, 0, sizeof(*store));
    store->flash = *flash;
    store->active = -1;
    store->next_seq = 1;
    for (uint32_t sector = 0; sector < 2u; ++sector) {
        uint32_t gen;
        if (read_header(store, sector, &gen) && (store->active < 0 || gen > store->generation)) {
            store->active = (int32_t)sector;
            store->generation = gen;
        }
    }
    if (store->active >= 0) {
        scan(store);
    }
    return 0;
}

uint32_t ctl_preset_free_bytes(const CtlPresetStore *store) {
    return store->active < 0 ? 0u : store->flash.sector_bytes - store->free_offset;
}

/* Copies the latest good record of every slot into the other sector, then makes it active. */
static int compact(CtlPresetStore *s) {
    const uint32_t target = s->active < 0 ? 0u : 1u - (uint32_t)s->active;
    if (s->flash.erase(s->flash.ctx, target) != 0) {
        ++s->errors;
        return -1;
    }
    uint32_t out = FIRST_RECORD;
    uint32_t max_seq = 0;
    for (int slot = 0; slot <= CTL_PRESET_POWER_ON; ++slot) {
        RecordInfo info;
        if (find_latest(s, slot, &info) == 0) {
            continue;
        }
        /* buf holds the record; pad its last word as erased flash. */
        memset(s->buf + CTL_PRESET_HEADER_BYTES + info.payload_len, 0xFF,
               info.total - CTL_PRESET_HEADER_BYTES - info.payload_len);
        if (s->flash.program(s->flash.ctx, target, out, s->buf, info.total) != 0) {
            ++s->errors;
            return -1;
        }
        out += info.total;
        max_seq = info.seq > max_seq ? info.seq : max_seq;
    }
    if (write_header(s, target, s->generation + 1u) != 0) {
        ++s->errors;
        return -1;
    }
    s->active = (int32_t)target;
    s->generation += 1u;
    s->free_offset = out;
    s->needs_compact = 0;
    if (max_seq >= s->next_seq) {
        s->next_seq = max_seq + 1u;
    }
    ++s->compactions;
    return 0;
}

static int region_blank(CtlPresetStore *s, uint32_t off, uint32_t n) {
    uint8_t w[CTL_FLASH_WORD];
    for (uint32_t i = 0; i < n; i += CTL_FLASH_WORD) {
        if (s->flash.read(s->flash.ctx, (uint32_t)s->active, off + i, w, CTL_FLASH_WORD) != 0) {
            return 0;
        }
        for (uint32_t k = 0; k < CTL_FLASH_WORD; ++k) {
            if (w[k] != 0xFFu) {
                return 0;
            }
        }
    }
    return 1;
}

/* Makes room for `total` bytes at free_offset in an active sector. */
static int make_room(CtlPresetStore *s, uint32_t total) {
    if (s->active < 0) {
        /* Blank flash: format sector 0 as generation 1. */
        if (s->flash.erase(s->flash.ctx, 0u) != 0 || write_header(s, 0u, 1u) != 0) {
            ++s->errors;
            return -1;
        }
        s->active = 0;
        s->generation = 1;
        s->free_offset = FIRST_RECORD;
        s->next_seq = 1;
    }
    for (int attempt = 0; attempt < 2; ++attempt) {
        if (!s->needs_compact && s->free_offset + total <= s->flash.sector_bytes &&
            region_blank(s, s->free_offset, total)) {
            return 0;
        }
        if (compact(s) != 0) {
            return -1;
        }
    }
    return -1;
}

/* Appends the record in buf (header fields from slot, payload filled in). */
static int append(CtlPresetStore *s, int slot, uint32_t payload_len, uint32_t count) {
    uint8_t *h = s->buf;
    put16(h, RECORD_MAGIC);
    h[2] = (uint8_t)slot;
    h[3] = FORMAT_VERSION;
    put32(h + 4, s->next_seq);
    put16(h + 8, payload_len);
    put16(h + 10, count);
    uint32_t crc = dsp_crc32(0u, h, 12u);
    crc = dsp_crc32(crc, h + CTL_PRESET_HEADER_BYTES, payload_len);
    put32(h + 12, crc);
    const uint32_t total = round_word(CTL_PRESET_HEADER_BYTES + payload_len);
    memset(h + CTL_PRESET_HEADER_BYTES + payload_len, 0xFF,
           total - CTL_PRESET_HEADER_BYTES - payload_len);
    const int r = s->flash.program(s->flash.ctx, (uint32_t)s->active, s->free_offset, h, total);
    s->free_offset += total; /* Written or torn, those words are used. */
    if (r != 0) {
        ++s->errors;
        return -1;
    }
    ++s->next_seq;
    ++s->writes;
    return 0;
}

static void put_name(uint8_t *dst, const char *name, size_t len) {
    memset(dst, 0, CTL_PRESET_NAME_LEN);
    for (size_t i = 0; i < len && i < CTL_PRESET_NAME_LEN; ++i) {
        dst[i] = (uint8_t)name[i];
    }
}

int ctl_preset_save(CtlPresetStore *store, int slot, const char *name, size_t name_len,
                    const CtlCore *core) {
    if (slot < 0 || slot > CTL_PRESET_POWER_ON) {
        return -1;
    }
    const uint8_t mask = slot_mask(slot);
    const uint32_t count = count_params(mask);
    if (make_room(store, record_bytes(count)) != 0) {
        return -1;
    }
    uint8_t *p = store->buf + CTL_PRESET_HEADER_BYTES;
    put_name(p, name, name_len);
    p += CTL_PRESET_NAME_LEN;
    for (size_t i = 0; i < ctl_param_count(); ++i) {
        const CtlParamDesc *d = ctl_param_desc(i);
        if ((d->flags & mask) == 0u) {
            continue;
        }
        uint32_t bits;
        memcpy(&bits, &core->value[i], sizeof(bits));
        put16(p, d->id);
        put16(p + 2, 0u);
        put32(p + 4, bits);
        p += ENTRY_BYTES;
    }
    return append(store, slot, CTL_PRESET_NAME_LEN + ENTRY_BYTES * count, count);
}

int ctl_preset_rename(CtlPresetStore *store, int slot, const char *name, size_t name_len) {
    RecordInfo info;
    if (slot < 0 || slot > CTL_PRESET_POWER_ON || find_latest(store, slot, &info) == 0) {
        return -1;
    }
    if (make_room(store, info.total) != 0 || find_latest(store, slot, &info) == 0) {
        return -1; /* Compaction may have moved it: find it again. */
    }
    put_name(store->buf + CTL_PRESET_HEADER_BYTES, name, name_len);
    return append(store, slot, info.payload_len, info.count);
}

int ctl_preset_info(CtlPresetStore *store, int slot, char *name, uint32_t *seq) {
    RecordInfo info;
    if (slot < 0 || slot > CTL_PRESET_POWER_ON || find_latest(store, slot, &info) == 0) {
        return -1;
    }
    for (size_t i = 0; i < CTL_PRESET_NAME_LEN; ++i) {
        const uint8_t c = store->buf[CTL_PRESET_HEADER_BYTES + i];
        name[i] = (c >= 0x20u && c < 0x7Fu) ? (char)c : (c == 0u ? '\0' : '?');
    }
    name[CTL_PRESET_NAME_LEN] = '\0';
    *seq = info.seq;
    return 0;
}

int ctl_preset_load(CtlPresetStore *store, int slot, CtlCore *core) {
    RecordInfo info;
    if (slot < 0 || slot > CTL_PRESET_POWER_ON || find_latest(store, slot, &info) == 0) {
        return -1;
    }
    const uint8_t mask = slot_mask(slot);
    const uint8_t *entries = store->buf + CTL_PRESET_HEADER_BYTES + CTL_PRESET_NAME_LEN;
    /* Two passes: the knob ownership modes first, so a knob's parameter is judged by the mode
     * being restored with it, not by the one in force before (their ids come later). */
    for (size_t k = 0; k < 2u * ctl_param_count(); ++k) {
        const size_t i = k % ctl_param_count();
        const CtlParamDesc *d = ctl_param_desc(i);
        const int is_mode = d->id >= CTL_ID_MODE_FIRST && d->id <= CTL_ID_MODE_LAST;
        if ((d->flags & mask) == 0u || is_mode != (k < ctl_param_count())) {
            continue;
        }
        float v = d->def; /* Missing from an older record: the default. */
        for (uint32_t e = 0; e < info.count; ++e) {
            if (get16(entries + ENTRY_BYTES * e) == d->id) {
                const uint32_t bits = get32(entries + ENTRY_BYTES * e + 4);
                memcpy(&v, &bits, sizeof(v));
                break;
            }
        }
        if (!isfinite(v)) {
            v = d->def;
        }
        (void)ctl_core_set(core, i, v, kCtlSrcPreset, NULL); /* Knob wins: refused, as meant. */
    }
    return 0;
}

int ctl_preset_restore(CtlPresetStore *store, CtlCore *core) {
    const int r = ctl_preset_load(store, CTL_PRESET_POWER_ON, core);
    core->settings_dirty = 0;
    return r;
}

void ctl_preset_tick(CtlPresetStore *store, CtlCore *core) {
    if (core->settings_dirty == 0u ||
        core->now_ms - core->last_change_ms < CTL_PRESET_SAVE_DELAY_MS) {
        return;
    }
    core->settings_dirty = 0; /* Cleared first: a failing flash is not retried every loop. */
    (void)ctl_preset_save(store, CTL_PRESET_POWER_ON, "power-on", 8u, core);
}
