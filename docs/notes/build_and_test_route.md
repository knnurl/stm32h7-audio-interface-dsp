# Design note: the build and test route

Batch 1. How one DSP block gets from an idea to a number measured on the target, and why the
route is built this way. Every later block follows it.

## Purpose

A claim about a DSP block ("it is correct", "it costs 12 cycles per sample") is only worth
making if the code that was checked is the code that runs on the device. The route makes that
true by construction.

## The route

```
tests/ref/<block>.py        Python reference model: the definition of correct
        |  compared by pytest, through ctypes
dsp/src/<block>.c           one C source, hardware-free
        |-> build/host: dsp_host.dll   (MSVC, PC)
        '-> build/fw:   dsp_cm7.elf    (GCC, Cortex-M7)
dsp/src/dsp_selftest.c      one fixed case per block, compiled into both
        |  PC: checked against the reference
        '  target: `bench` prints cycles and a checksum, `vec` dumps the output
tools/target_test.py        compares target with PC: checksum (fixed point) or tolerance (float)
```

1. **Reference model first.** `tests/ref/` holds a model per block, in float64 or in Python
   integers, written from the block's defining equation and not from the C code.
2. **One C source, two builds.** `dsp/` has no HAL, no allocation and no I/O, so the same file
   compiles for the PC and the M7. The PC build is a DLL that pytest loads with ctypes.
3. **Shared self-test cases.** `dsp_selftest.c` fixes one input and one parameter set per block.
   Because the case is C code inside the library, the target cannot run a different test from
   the PC.
4. **Two-step agreement.** The PC library is checked against the reference; the target is
   checked against the PC library. A target that agrees with the PC therefore agrees with the
   reference, to the sum of the two tolerances.

## Choices and what was rejected

- **ctypes and a DLL, not a C test framework.** The reference models need numpy and scipy, so
  the comparison has to happen in Python anyway. Rejected: doctest or Unity with stored vectors,
  which adds vector files that drift from the models.
- **Test inputs generated in C, not sent to the target.** `dsp_testsig` makes noise from a
  32-bit linear congruential generator in integer arithmetic, so the input is bit-identical on
  both sides without transferring anything. Rejected: uploading vectors over the serial port,
  which is slow and needs a protocol before the first block exists.
- **Checksum for fixed point, dump for float.** A CRC-32 of the output proves bit-exactness in
  one line of console output. Float cannot be held to that across compilers, so its output is
  dumped as hex words and compared within a tolerance.
- **The comparison logic is separate from the serial port** (`tools/target_protocol.py`), so it
  is unit-tested without a board, with "target" text generated from the PC library.

## Numerical behaviour

- **Float agreement between MSVC x64 and GCC on the M7.** Both do IEEE single precision. They
  differ where a compiler fuses a multiply and an add, and in C library functions (`expf`,
  `powf`). Fused contraction is off on both sides (`/fp:precise`, `-ffp-contract=off`) until
  batch 3 measures what it costs. Library calls stay in init and coefficient code.
- **The tolerance is -120 dBFS.** The first block showed why it is not tighter: see
  `docs/notes/gain.md`.

## Measured

| Item | Value | How |
|---|---|---|
| Host tests | 28 pass | `python -m pytest` |
| M7 image | 20 152 B flash, 33 608 B of DTCM | `cmake --build --preset fw` |
| M4 image | 1 268 B flash | same |
| Supply setting in both images | direct SMPS: start-up clears LDOEN in PWR_CR3 and waits for ACTVOSRDY | disassembly of `ExitRun0Mode` |
| Cycles per sample on the target | not measured: no board was attached | `python tools/target_test.py --port COMx` |

## Open questions

- Whether the float cases come out bit-identical on the target, or only within tolerance.
- The M7's real clock: the banner prints cycles per millisecond measured against SysTick, which
  should read 400 000.
