# Plan: planning docs for the STM32H755 DSP audio interface

## Context

The owner wants to practise embedded DSP in line with a DSP Engineer role (DSP on hardware audio
products: embedded processors, real-time constraints, integration with firmware and hardware).
Together with Claude he designs the PCB and writes the firmware. The board also becomes his home
studio USB sound interface. The outcome of this step is a set of planning documents in
`C:\Users\ses634\Desktop\Projects\DSP` (empty today): **docs only, no code, no KiCad, no commits.**

## Decisions from the interview

| Topic | Decision |
|---|---|
| Goal | Interview portfolio piece: one demoable device, measured results, clean repo and write-up |
| Work split | Claude writes code and docs; owner reviews. Each milestone ships a design note per DSP block and one small exercise the owner codes himself |
| Device | Concept A, full DSP interface: input strips, DSP monitor mixer with reverb, monitor stage with room-correction FIR, headphone stage |
| Analogue I/O | 2 balanced line in; 4 out (monitors L/R, headphones L/R). No mic preamp, no phantom, no Hi-Z |
| Other I/O | USB UAC2 audio, USB control link to a PC app, front panel, S/PDIF in and out |
| Algorithms | Filters, dynamics, FFT and partitioned convolution, time-based and nonlinear, fixed-point variants |
| Processor | STM32H755 (owner has the Nucleo). M7 runs audio DSP and USB audio; M4 runs control, UI and housekeeping (own milestone, starts idle) |
| Hardware path | Rev A = audio shield for the Nucleo-H755 (converters, analogue, clocks, S/PDIF, power); USB FS through the Nucleo. Rev B = integrated H755 + ULPI PHY (USB HS, 96 kHz, 4x4 channels) |
| Analogue grade | Mid-grade, measured honestly |
| PCB build | 4-layer, JLC Economic PCBA for SMT, through-hole parts hand-fitted |
| Power | External 12 V DC; USB for data only |
| Measurement | Borrowed university lab analyser and lab measurement mic; day to day: digital tests and DAC-to-ADC loopback |
| Language | C11 DSP library (builds on PC and target), C firmware; Python reference models and test harness |
| Repo | Public GitHub, MIT licence (GitHub repo created only on the owner's go) |
| Timeline | No deadline; milestones, not dates |

## Defaults I am choosing (change any of them at approval)

- **Priorities for trade-offs:** 1 measured correctness, 2 real-time robustness (no xruns),
  3 monitoring latency, 4 audio quality, 5 cost, 6 feature count.
- **Sample rates:** 44.1, 48, 88.2 and 96 kHz from two audio oscillators on the shield
  (22.5792 and 24.576 MHz). The oscillator is the master clock. The codec and the SAI both run
  from it, through I2S_CKIN as the SAI kernel clock [Verify].
- **Rev A USB bandwidth:** USB FS carries 2 record and 2 playback channels at 96 kHz with 3-byte
  subslots. That is about 582 B per frame each way, against about 1350 B of periodic bandwidth
  per frame [Verify]. Recording S/PDIF as well needs 48 kHz on rev A, or rev B with USB HS.
- **Libraries:** TinyUSB (MIT) for UAC2 with an async feedback endpoint [Verify 3-byte subslot
  support]; ST HAL/LL (BSD-3); CMSIS-DSP (Apache-2.0) as the yardstick our own kernels are
  benchmarked against; FreeRTOS (MIT) on the M4 only.
- **Real-time model on the M7:**
  - Bare metal, SAI DMA ping-pong, DSP running in the DMA interrupt.
  - Block size 16 at 96 kHz.
  - State in DTCM, hot kernels in ITCM, DMA buffers in a non-cacheable MPU region of D2 SRAM.
  - No allocation after init. CPU load and xrun counters exported to the host.
- **Toolchain:**
  - CMake with arm-none-eabi-gcc from STM32CubeCLT. CubeMX is used only for the pin plan and
    the clock tree, and its output lives in `vendor/`.
  - Host build of the DSP library with CMake and MSVC, loaded into Python through ctypes.
  - Python 3 with numpy, scipy, pytest, sounddevice and matplotlib.
- **Test rule:** fixed-point kernels must match bit-exactly against a Python integer model.
  Float kernels must match within a stated tolerance, because MSVC x64 and GCC on the M7 may
  contract FMAs differently. Target outputs are compared against the host on stored vectors.
- **Codec breakouts for early firmware:** PCM1808 ADC and PCM5102A DAC modules (about £10
  [Verify]) on the Nucleo. Firmware then runs before the shield exists. MCLK comes from PLL3 for
  now.
- **Enclosure:** rev A is open frame on standoffs; the enclosure belongs to rev B.
- **Writing conventions:** as in Psyight: British English, no em dashes, sentence case for UI
  labels, `[Verify]` on unverified claims.

## Files to create in `C:\Users\ses634\Desktop\Projects\DSP`

1. `README.md`: project pitch, the concept A signal-flow diagram, status table, links to the docs.
2. `CLAUDE.md`: project rules for future sessions:
   - priorities and the work split, including the review pack required per milestone;
   - C11 conventions: `snake_case`, units in names (`_hz`, `_ms`, `_samples`, `_db`), `kName`
     constants;
   - the block API `x_init / x_reset / x_process(state, in, out, n)`, with each header listing
     assumptions, latency in samples and measured cycles per sample;
   - real-time rules, test rules, writing conventions, and the ask-before list (dependencies,
     scope, part changes, orders);
   - commands, kept accurate as they come into existence.
3. `LICENSE`: MIT, copyright holder the owner's name.
4. `docs/SPEC.md`: requirements and design. Sections:
   1. Purpose, audience, non-goals. Non-goals: mic preamps, Hi-Z input, a custom ASIO driver,
      network audio.
   2. Priorities, plus the signal flow of concept A.
   3. Requirements tables:
      - analogue levels: +4 dBu nominal, max level target [Verify against rails];
      - sample rates;
      - latency targets (analogue in to monitor out, USB round trip);
      - CPU budget: M7 worst case under 70 % at 96 kHz;
      - robustness: no xruns over 8 h;
      - mid-grade analogue targets.
   4. Hardware rev A shield, block by block:
      - power: 12 V in, protection, ±15 V, LDOs;
      - clocks;
      - converter choice: trade study between AK4619VN, CS42448, PCM3168A and a separate
        ADC/DAC pair, judged on dynamic range, TDM, 96 kHz, package, LCSC stock and price
        [Verify all];
      - balanced input receiver, output driver with mute relay, headphone amp;
      - S/PDIF transceivers;
      - front-panel header;
      - Nucleo morpho pin plan, checked against the Nucleo user manual's solder-bridge and
        conflict table (Ethernet RMII, VCP, USB) [Verify];
      - layout and grounding rules.
   5. Rev B delta: integrated H755, USB3320 ULPI, USB HS, enclosure.
   6. Firmware architecture:
      - memory map and cache policy;
      - interrupt priorities;
      - USB to audio buffering and async feedback;
      - sample-rate switching;
      - M7/M4 split over shared SRAM with hardware semaphores;
      - parameter registry and control protocol.
   7. DSP blocks, each with algorithm, precision variants, latency, test method and references:
      - gain smoothing;
      - biquad PEQ and HPF (float TDF-II, Q31 DF-I with error feedback);
      - compressor, gate, look-ahead true-peak limiter;
      - saturation with polyphase oversampling, compared against ADAA;
      - matrix monitor mixer;
      - FDN reverb;
      - BS.1770 metering;
      - uniformly partitioned convolution;
      - headphone crossfeed;
      - software ASRC for S/PDIF in.
   8. Verification strategy:
      - host tests and fixed-point bit-exact tests;
      - on-target vector tests;
      - cycle benchmarks;
      - latency measurement methods (scope, loopback);
      - lab characterisation protocol (frequency response, THD+N, dynamic range, crosstalk, max
        level, AES17-style [Verify]).
   9. Assumptions to verify, collected from every `[Verify]`.
   10. Decision log, seeded with this interview's decisions.
5. `docs/PLAN.md`: milestones. Each one has a goal, "done when" criteria, a verification command
   or measurement, the design notes it produces, and the owner's exercise.

| # | Milestone | Done when (summary) |
|---|---|---|
| M0 | Foundation | Host DSP lib builds and `ctest`/pytest pass; M7 firmware builds via CMake, runs on the Nucleo, reports DWT cycle counts; CI builds both |
| M1 | Audio pass-through on breakouts | SAI DMA ping-pong at 48/96 kHz, cache-safe; latency and CPU load measured with a scope |
| M2 | Filters | Gain smoothing, biquads float and Q31, HPF, 4-band PEQ, glitch-free coefficient updates; matched to scipy; cycle table; float vs Q31 noise study at 20 Hz / 96 kHz |
| M3 | USB audio (FS) | Windows in-box UAC2 enumerates; 2x2 at 96 kHz; feedback holds buffer fill steady for 1 h, no xruns; round-trip latency measured by loopback |
| M4 | Shield rev A design | Converter trade study; schematic and layout reviewed against a checklist; ERC/DRC clean; JLC order files ready. **Owner places the order** |
| M5 | Dynamics and saturation | Compressor, gate, true-peak limiter, oversampled saturation; aliasing measured digitally |
| M6 | Shield bring-up and lab session | Rails, clocks, codec, mute; characterised on the lab analyser; results vs targets written up |
| M7 | Strips, monitor mixer, reverb, metering, host control | Full concept A path minus room correction; parameter registry; Python control app; analogue in to out latency measured |
| M8 | Room correction | Sweep measured with the lab mic, FIR designed in Python, uploaded; partitioned convolution on M7 at one-block latency; room re-measured |
| M9 | S/PDIF and ASRC | SPDIFRX and S/PDIF out; software ASRC with rate-tracking loop; conversion THD+N measured digitally |
| M10 | Dual-core split and front panel | Control, UI and protocol moved to M4 under FreeRTOS; OLED and encoders work |
| M11 | Rev B integrated board | H755 + ULPI USB HS; 4x4 at 96 kHz; re-characterised; enclosure |
| M12 | Portfolio write-up | Spec sheet, latency and CPU tables, fixed vs float study, demo video, talking points |

M4 runs alongside M2 and M3, so the shield is in fabrication while the firmware matures.

6. After writing, publish a private browser page (Artifact) with the system overview: the signal
   flow, the rev A and rev B split, and the milestone map. This was the browser view the owner
   asked for during the interview.

No git init, commit or GitHub repo until the owner says so.

## Verification of this step

- Every row of "Decisions from the interview" appears in `docs/SPEC.md` (decision log) and is
  consistent across README, CLAUDE.md and PLAN.md.
- Every price, bandwidth, pin and part-performance claim carries `[Verify]` and is listed in the
  SPEC's "Assumptions to verify" section.
- A search for em dashes in `DSP/` returns nothing; spelling is British.
- Nothing but Markdown and LICENSE is created; no code or hardware files.
- The owner reads SPEC and PLAN and either approves them or lists changes; changes go into the
  decision log.
