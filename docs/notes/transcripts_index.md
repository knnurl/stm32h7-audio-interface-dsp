# Phil's Lab transcripts: index

The owner added 29 transcripts of Phil's Lab videos on 2026-11-17 and asked that they be taken
as reliable notes. They are in `docs/transcripts_no_timestamp/` (read these) and
`docs/transcripts/` (the same text with timestamps, for finding the place in a video). Both
folders are gitignored: the text is the author's, and this repository is meant to go public.

## How to use them

- Before starting a batch, read the transcripts listed for it below and say in the batch's design
  notes what was taken from them.
- Treat the engineering content as reliable. Two limits:
  - They are automatic captions. Words and numbers are sometimes wrong ("I quad" for "biquad"),
    and equations, schematics and code shown on screen are not in the text. Check any number or
    formula before using it.
  - The videos use other hardware (a custom STM32 guitar pedal, other codecs, mostly single-core
    parts). Pin, clock and memory details do not carry over to the Nucleo-H755ZI-Q. This
    project's SPEC decisions and its own measurements win where they differ.
- A claim taken from a transcript and not yet checked here carries `[Verify]` like any other.

## By batch

| Batch | Transcripts |
|---|---|
| 2: audio pass-through | STM32 I2S ADC DMA & Double Buffering (#55); How To Write A Driver, Audio CODEC & I2C (#142); Digital Audio Processing with STM32 #1, Introduction and Filters |
| 3: filters | Biquad Filters (#172); Audio EQ Software Implementation (#89); IIR Filters, Theory and Implementation (#32); Bilinear Transform IIR Filter Design; Real-Time Software Implementation of Analog Filters (#20); Z-Transform, Practical Applications (#27); The Simplest Digital Filter (#92); Notch Filters (#49); All-Pass Filter Software Implementation (#162) |
| 5: shield design | Mini 6-Layer Mixed-Signal Hardware Design Walkthrough (#78); How To Write A Driver (#142) for the codec's control interface |
| 6: dynamics and saturation | Audio Compressor Software Implementation; Noise Gate (#58); Recursive RMS (#103); DSP Overdrive Algorithm (#117); DSP Overdrive, Asymmetrical Clipping (#153); Decimation Filters (#42) for the oversampler |
| 8: mixer, reverb, metering | Comb Filters & Delay Lines (#124); Delay-Based Audio FX (#140); All-Pass Filter (#162); Tremolo Effect; Recursive RMS (#103) |
| 9: room correction | Real-Time Impulse Response Simulation (#126); STM32 Fast Fourier Transform, CMSIS DSP FFT (#111); STM32 Real-Time FIR Filter Implementation, CMSIS DSP (#141) |
| 10: S/PDIF and ASRC | Decimation Filters (#42) |
| Not used by this project | Sensor Fusion #1 to #4 (#33, #34, #37, #73): accelerometers, complementary filter, extended Kalman filter |

## Read in full

| Date | Transcripts | For | Where the findings went |
|---|---|---|---|
| 2026-11-17 | #172, #89, #32, Bilinear Transform, #20, #27, #92, #49, #162 | Batch 3 | `biquad.md`, `coefficient_design.md`, `tone.md` |

The rest of the table above is by title only.
