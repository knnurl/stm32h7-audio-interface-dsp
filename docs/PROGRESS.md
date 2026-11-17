# Progress

The handoff log, newest entry first. Each entry: what was done, measured numbers, exact
commands, what the owner decides or does next.

## 2026-11-17: batch 0, project documents

Done: `README.md`, `LICENSE`, `.gitignore`, `CLAUDE.md`, `docs/SPEC.md`, `docs/PLAN.md`, this
file, and a local git repository on `main`. Nothing built.

The interview plan, the assessment and the batch specification were already in `docs/`.

Numbers: none measured. The SPEC's cycle budget (3.4) is all estimates, and its total (3630
cycles per sample) is over the 70 % ceiling (2916). Nothing is cut on estimates; batches 3 and 6
replace the largest rows with measurements.

For the owner to confirm or change (SPEC 3.2 and 3.3, marked "proposed"):

| Target | Proposed |
|---|---|
| Analogue in to monitor out latency at 96 kHz, without the room FIR | under 1.5 ms |
| USB round trip at 48 kHz | under 10 ms |
| M7 worst-case load at 96 kHz | under 70 % |
| Input level at 0 dBFS | +20 dBu |
| Monitor output level at 0 dBFS | +18 dBu |
