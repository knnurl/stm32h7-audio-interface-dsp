/* CRC-32 as zlib computes it (reflected polynomial 0xEDB88320, initial value and final XOR of
 * all ones). The PC and the target compare block outputs by this checksum. */
#ifndef DSP_CRC32_H
#define DSP_CRC32_H

#include <stddef.h>
#include <stdint.h>

/* Start with crc 0; pass the previous result to continue over more data. */
uint32_t dsp_crc32(uint32_t crc, const void *data, size_t n_bytes);

#endif
