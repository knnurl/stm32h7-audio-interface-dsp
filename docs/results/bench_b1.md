# Batch 1: cycles on the target

**Not measured yet.** No board was attached when batch 1 was written (STM32_Programmer_CLI found
no ST-LINK on 2026-11-17).

To fill this in, with the Nucleo-H755ZI-Q on its ST-LINK USB port:

```
powershell -ExecutionPolicy Bypass -File tools/flash.ps1
python tools/target_test.py --port COMx --results docs/results/bench_b1_table.md
```

Then copy the banner's `clock` line and the table here.

What to expect, as estimates only: `gain_f32` at about 8 to 12 cycles per sample (the case's
figure includes two set-up calls with `expf` and `powf`, spread over 1024 samples), and
`measured_cycles_per_ms=400000` in the banner.
