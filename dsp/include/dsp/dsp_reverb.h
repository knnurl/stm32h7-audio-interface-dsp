/* Reverb: an 8-line feedback delay network (Jot and Chaigne's structure), wet only, on the
 * monitor mixer's send and return.
 *
 * Per sample: s_i = line_i read at L_i (two lines modulated);  f_i = absorbent filter_i(s_i);
 * v = H f, H the 8 x 8 Hadamard matrix / sqrt(8);  line_i <- v_i + input injection.
 * Outputs: two orthogonal sign patterns over the s_i, so left and right are decorrelated.
 *
 * Matrix: Hadamard, not Householder. Both are orthogonal (lossless) and cheap: Hadamard by a fast
 * transform, 24 additions and 8 multiplies; Householder (I - 2/N 1 1^T) in 16 operations. But a
 * Householder matrix of order 8 keeps 0.75 of each line in itself on every pass, so the echo
 * density builds slowly; every Hadamard entry is +/-1/sqrt(8), so each pass spreads every line
 * evenly into all eight. Echo density is what makes a reverb sound smooth rather than fluttery,
 * so it decides (measured in tests/unit/test_reverb.py and docs/notes/reverb.md).
 * Lengths: base times 19.3, 23.9, 27.1, 31.7, 35.3, 39.7, 43.9 and 47.9 ms, each rounded to the
 * next prime number of samples at the running rate, so the lengths are mutually prime at every
 * rate and no two lines' echoes keep coinciding.
 * Absorbent filter per line (Jot): a one-pole low-pass y = b0 x + a1 y1 whose gain at DC is
 * g_lo = 10^(-3 L / (fs T_lo)) and at Nyquist g_hi = 10^(-3 L / (fs T_hi)):
 *   a1 = (g_lo - g_hi) / (g_lo + g_hi),  b0 = g_lo (1 - a1).
 * Every line then loses 60 dB in T_lo at low frequencies and in T_hi at high ones; in between
 * the decay time moves smoothly from one to the other.
 * Modulation: lines 2 and 6 are read at L +/- 0.3 ms, at 0.31 and 0.43 Hz, through third-order
 * Lagrange reads, which breaks up the metallic ringing of fixed lengths.
 * Pre-delay: 0 to 100 ms, stereo.
 *
 * Memory: caller-provided; dsp_reverb_f32_mem_needed(fs) floats (about 26 900 at 96 kHz for
 * the lines and 19 200 for the pre-delay: 184 KB; see docs/results/b8b_memory.md).
 * Assumptions: stereo; any block size. Latency: the pre-delay. Cycles: not yet measured.
 */
#ifndef DSP_REVERB_H
#define DSP_REVERB_H

#include "dsp/dsp_delayline.h"
#include "dsp/dsp_lfo.h"

#include <stddef.h>
#include <stdint.h>

enum { kDspReverbLines = 8 };

typedef struct {
    float sample_rate_hz;
    DspDelaylineF32 line[kDspReverbLines];
    DspDelaylineF32 pre[2];
    int32_t len[kDspReverbLines];
    float b0[kDspReverbLines];
    float a1[kDspReverbLines];
    float z[kDspReverbLines];
    DspLfoF32 mod[2];
    float mod_depth;    /* Samples. */
    float rt60_low_s;
    float rt60_high_s;
    int32_t predelay;   /* Samples. */
    int32_t max_predelay;
} DspReverbF32;

int32_t dsp_reverb_f32_mem_needed(float sample_rate_hz);
/* Returns 0, or -1 if the memory is smaller than dsp_reverb_f32_mem_needed. Defaults: 2 s low,
 * 1 s high, 10 ms pre-delay. */
int32_t dsp_reverb_f32_init(DspReverbF32 *rev, float sample_rate_hz, float *mem, int32_t mem_len);
void dsp_reverb_f32_reset(DspReverbF32 *rev, int32_t clear_memory);
/* Decay times to -60 dB at low and high frequency; low in [0.1, 20] s, high in [0.05, low]. */
void dsp_reverb_f32_set_decay(DspReverbF32 *rev, float rt60_low_s, float rt60_high_s);
void dsp_reverb_f32_set_predelay_ms(DspReverbF32 *rev, float ms);
void dsp_reverb_f32_process(DspReverbF32 *rev, const float *in_l, const float *in_r,
                            float *out_l, float *out_r, size_t n_frames);

#endif
