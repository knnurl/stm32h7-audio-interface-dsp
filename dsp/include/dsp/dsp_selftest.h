/* One fixed test case per block, compiled into both the PC library and the firmware, so the two
 * run exactly the same code on exactly the same input. The PC checks each case against its
 * Python reference; the output on the target is then checked against the PC (checksum for fixed
 * point, tolerance for float).
 *
 * Samples are 4 bytes in every format (float or Q31), so buffers are arrays of 32-bit words.
 * A case builds the state of its block (on the stack, or in a static for the large ones):
 * the time of a run includes that set-up. Not reentrant.
 */
#ifndef DSP_SELFTEST_H
#define DSP_SELFTEST_H

#include <stddef.h>
#include <stdint.h>

enum { kDspSelftestFrames = 1024 };

typedef enum { kDspFmtF32 = 0, kDspFmtQ31 = 1 } DspFmt;

size_t dsp_selftest_count(void);
/* NULL when the index is out of range. */
const char *dsp_selftest_name(size_t index);
/* A DspFmt, or -1 when the index is out of range. */
int dsp_selftest_fmt(size_t index);
/* Fills `in` with the input of the case: kDspSelftestFrames words. */
void dsp_selftest_input(size_t index, void *in);
/* Runs the case: kDspSelftestFrames words in, the same number out. */
void dsp_selftest_run(size_t index, const void *in, void *out);

#endif
