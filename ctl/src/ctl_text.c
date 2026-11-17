#include "ctl/ctl_text.h"

void ctl_line_clear(CtlLine *line) {
    line->len = 0;
    line->overflow = 0;
    line->text[0] = '\0';
}

void ctl_line_char(CtlLine *line, char c) {
    if (line->len >= CTL_LINE_MAX) {
        line->overflow = 1;
        return;
    }
    line->text[line->len++] = c;
    line->text[line->len] = '\0';
}

void ctl_line_mem(CtlLine *line, const char *s, size_t n) {
    for (size_t i = 0; i < n; ++i) {
        ctl_line_char(line, s[i]);
    }
}

void ctl_line_str(CtlLine *line, const char *s) {
    while (*s != '\0') {
        ctl_line_char(line, *s++);
    }
}

static void line_u64(CtlLine *line, uint64_t v, int min_digits) {
    char digits[20];
    int n = 0;
    do {
        digits[n++] = (char)('0' + (int)(v % 10u));
        v /= 10u;
    } while (v != 0u || n < min_digits);
    while (n > 0) {
        ctl_line_char(line, digits[--n]);
    }
}

void ctl_line_uint(CtlLine *line, uint32_t v) { line_u64(line, v, 1); }

void ctl_line_int(CtlLine *line, int32_t v) {
    if (v < 0) {
        ctl_line_char(line, '-');
        line_u64(line, (uint64_t)(-(int64_t)v), 1);
    } else {
        line_u64(line, (uint64_t)v, 1);
    }
}

void ctl_line_hex(CtlLine *line, uint32_t v) {
    static const char kHex[] = "0123456789abcdef";
    ctl_line_str(line, "0x");
    for (int shift = 28; shift >= 0; shift -= 4) {
        ctl_line_char(line, kHex[(v >> shift) & 0xFu]);
    }
}

void ctl_line_float(CtlLine *line, float v) {
    if (v != v) {
        ctl_line_str(line, "nan");
        return;
    }
    double d = (double)v;
    if (d >= 1e9 || d <= -1e9) {
        ctl_line_str(line, "big");
        return;
    }
    const int negative = d < 0.0;
    if (negative) {
        d = -d;
    }
    /* Round half away from zero at the fourth decimal. */
    const uint64_t scaled = (uint64_t)(d * 10000.0 + 0.5);
    const uint64_t whole = scaled / 10000u;
    uint32_t frac = (uint32_t)(scaled % 10000u);
    if (negative && scaled != 0u) {
        ctl_line_char(line, '-');
    }
    line_u64(line, whole, 1);
    if (frac != 0u) {
        int digits = 4;
        while (frac % 10u == 0u) {
            frac /= 10u;
            --digits;
        }
        ctl_line_char(line, '.');
        line_u64(line, frac, digits);
    }
}

static int is_digit(char c) { return c >= '0' && c <= '9'; }

int ctl_parse_uint(const char *s, size_t len, uint32_t *out) {
    if (len == 0u || len > 9u) {
        return -1;
    }
    uint32_t v = 0;
    for (size_t i = 0; i < len; ++i) {
        if (!is_digit(s[i])) {
            return -1;
        }
        v = v * 10u + (uint32_t)(s[i] - '0');
    }
    *out = v;
    return 0;
}

int ctl_parse_float(const char *s, size_t len, float *out) {
    size_t i = 0;
    int negative = 0;
    if (i < len && (s[i] == '+' || s[i] == '-')) {
        negative = s[i] == '-';
        ++i;
    }
    double mantissa = 0.0;
    int exp10 = 0;
    int digits = 0;
    int significant = 0;
    while (i < len && is_digit(s[i])) {
        if (significant < 17) {
            mantissa = mantissa * 10.0 + (double)(s[i] - '0');
            if (mantissa != 0.0) {
                ++significant;
            }
        } else {
            ++exp10; /* Further digits only scale. */
        }
        ++digits;
        ++i;
    }
    if (i < len && s[i] == '.') {
        ++i;
        while (i < len && is_digit(s[i])) {
            if (significant < 17) {
                mantissa = mantissa * 10.0 + (double)(s[i] - '0');
                --exp10;
                if (mantissa != 0.0) {
                    ++significant;
                }
            }
            ++digits;
            ++i;
        }
    }
    if (digits == 0) {
        return -1;
    }
    if (i < len && (s[i] == 'e' || s[i] == 'E')) {
        ++i;
        int exp_negative = 0;
        if (i < len && (s[i] == '+' || s[i] == '-')) {
            exp_negative = s[i] == '-';
            ++i;
        }
        int e = 0;
        int exp_digits = 0;
        while (i < len && is_digit(s[i])) {
            if (e < 1000) {
                e = e * 10 + (s[i] - '0');
            }
            ++exp_digits;
            ++i;
        }
        if (exp_digits == 0) {
            return -1;
        }
        exp10 += exp_negative ? -e : e;
    }
    if (i != len) {
        return -1;
    }
    /* Scale by powers of ten; anything outside +/-1e40 is out of every range anyway. */
    if (exp10 > 40) {
        exp10 = 40;
    } else if (exp10 < -60) {
        mantissa = 0.0;
        exp10 = 0;
    }
    double scale = 1.0;
    const int n = exp10 < 0 ? -exp10 : exp10;
    for (int k = 0; k < n; ++k) {
        scale *= 10.0;
    }
    double v = exp10 < 0 ? mantissa / scale : mantissa * scale;
    if (v > 3.0e38) {
        v = 3.0e38;
    }
    *out = (float)(negative ? -v : v);
    return 0;
}
