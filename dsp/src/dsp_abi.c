/* Struct sizes, so the Python tests can check that their ctypes mirrors of the library's structs
 * have the same layout as the compiler's. A mirror that is wrong by one field would otherwise
 * read and write the wrong bytes without any error. Not used by the firmware. */
#include "dsp/dsp_comp.h"
#include "dsp/dsp_env.h"
#include "dsp/dsp_gate.h"
#include "dsp/dsp_limiter.h"
#include "dsp/dsp_oversample.h"
#include "dsp/dsp_peq.h"
#include "dsp/dsp_saturate.h"
#include "dsp/dsp_tone.h"

#include <string.h>

size_t dsp_abi_sizeof(const char *name);

size_t dsp_abi_sizeof(const char *name) {
    static const struct {
        const char *name;
        size_t size;
    } kSizes[] = {
        {"DspBiquadF32", sizeof(DspBiquadF32)},
        {"DspBiquadQ31", sizeof(DspBiquadQ31)},
        {"DspPeqF32", sizeof(DspPeqF32)},
        {"DspToneF32", sizeof(DspToneF32)},
        {"DspEnvF32", sizeof(DspEnvF32)},
        {"DspCompF32", sizeof(DspCompF32)},
        {"DspGateF32", sizeof(DspGateF32)},
        {"DspHalfbandUpF32", sizeof(DspHalfbandUpF32)},
        {"DspHalfbandDownF32", sizeof(DspHalfbandDownF32)},
        {"DspOversampleF32", sizeof(DspOversampleF32)},
        {"DspSaturatorF32", sizeof(DspSaturatorF32)},
        {"DspLimiterF32", sizeof(DspLimiterF32)},
    };
    for (size_t i = 0; i < sizeof(kSizes) / sizeof(kSizes[0]); ++i) {
        if (strcmp(kSizes[i].name, name) == 0) {
            return kSizes[i].size;
        }
    }
    return 0;
}
