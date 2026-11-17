#include "dsp/dsp_crc32.h"

/* Four bits at a time: a 16-entry table keeps the cost and the size small. */
static const uint32_t kCrcTable[16] = {
    0x00000000u, 0x1DB71064u, 0x3B6E20C8u, 0x26D930ACu, 0x76DC4190u, 0x6B6B51F4u,
    0x4DB26158u, 0x5005713Cu, 0xEDB88320u, 0xF00F9344u, 0xD6D6A3E8u, 0xCB61B38Cu,
    0x9B64C2B0u, 0x86D3D2D4u, 0xA00AE278u, 0xBDBDF21Cu};

uint32_t dsp_crc32(uint32_t crc, const void *data, size_t n_bytes) {
    const uint8_t *bytes = (const uint8_t *)data;
    crc = ~crc;
    for (size_t i = 0; i < n_bytes; ++i) {
        crc ^= bytes[i];
        crc = kCrcTable[crc & 0x0Fu] ^ (crc >> 4);
        crc = kCrcTable[crc & 0x0Fu] ^ (crc >> 4);
    }
    return ~crc;
}
