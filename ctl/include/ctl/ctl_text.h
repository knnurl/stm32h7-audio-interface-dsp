/* Text for the control protocol without stdio: a bounded line builder, and number formatting and
 * parsing that behave the same on the PC and the target (no locale, no newlib printf).
 */
#ifndef CTL_TEXT_H
#define CTL_TEXT_H

#include <stddef.h>
#include <stdint.h>

#define CTL_LINE_MAX 320

/* A line being built. Appends past the end are dropped and set `overflow`; the text stays
 * NUL-terminated. */
typedef struct {
    char text[CTL_LINE_MAX + 1];
    size_t len;
    int overflow;
} CtlLine;

void ctl_line_clear(CtlLine *line);
void ctl_line_str(CtlLine *line, const char *s);
void ctl_line_mem(CtlLine *line, const char *s, size_t n);
void ctl_line_char(CtlLine *line, char c);
void ctl_line_uint(CtlLine *line, uint32_t v);
void ctl_line_int(CtlLine *line, int32_t v);
/* Up to 4 decimals, trailing zeros removed: 0.5, -12, 20000, 0.0001. NaN gives "nan",
 * magnitudes of 1e9 and over give "big". */
void ctl_line_float(CtlLine *line, float v);
void ctl_line_hex(CtlLine *line, uint32_t v);

/* Parses [+-]digits[.digits][(e|E)[+-]digits] spanning exactly `len` bytes. 0 on success. */
int ctl_parse_float(const char *s, size_t len, float *out);
/* Parses decimal digits spanning exactly `len` bytes, at most 9 of them. 0 on success. */
int ctl_parse_uint(const char *s, size_t len, uint32_t *out);

#endif
