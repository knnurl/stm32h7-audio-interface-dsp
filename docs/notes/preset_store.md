# Design note: the preset store

Batch 8a. `ctl_preset`, `ctl_flash_sim` (PC), `fw/cm7/src/flash_store.c` (target).

## Purpose

Eight presets and a power-on record, in on-chip flash, that survive a power cut at any moment
and a firmware update that adds or removes parameters.

## Layout

Two sectors: the last two of flash bank 2 (sectors 6 and 7, 128 KB each, 0x081C0000 and
0x081E0000). The M4's linker script stops at 768 KB, before them.

- **Sector header**, one 32-byte flash word at offset 0: magic `PSET`, generation, format
  version, CRC-32. The sector with a valid header and the higher generation holds the log.
- **Records**, appended from offset 32, each starting on a flash word:

| Bytes | Field |
|---|---|
| 0-1 | magic 0xC7A1 |
| 2 | slot: 0 to 7 presets, 8 the power-on record |
| 3 | format version (1) |
| 4-7 | sequence number |
| 8-9 | payload length |
| 10-11 | entry count |
| 12-15 | CRC-32 (zlib) of bytes 0 to 11 and the payload |
| 16-31 | name, 16 bytes |
| then | entries: id (2 bytes), 0 (2), value (float32, 4) |

  The rest of the last flash word is left as erased flash. All fields little-endian, written
  byte by byte, so the layout does not depend on the compiler. `tests/ref/ctl.py` encodes and
  decodes it independently, and a test checks the C store writes the same bytes.

## Rules

- **The last good record of a slot wins.** A record with a bad CRC (torn by a power cut, or
  decayed) is skipped, so the slot falls back to its previous record, then to the defaults.
- **A header that cannot be trusted** (bad magic, impossible length) ends the scan: nothing after
  it is used, and the next write compacts first.
- **Every write checks that its words are erased** before programming (the H7 keeps ECC per
  256-bit word and refuses to program a word twice).
- **Compaction** when a write does not fit: erase the other sector, copy the latest good record
  of each slot, then write that sector's header with generation + 1. The header goes last, so a
  power cut at any point leaves the old sector in charge; the half-written one is erased by the
  next compaction.
- **By id**: unknown ids in a record are ignored; parameters missing from it take their default.
- **Knob modes first**: a load applies the mode parameters before the rest, so a knob's value is
  judged by the mode being restored with it (bug found by `test_power_on_record_respects_knob_wins`).
- **Power-on record**: written 2 s after the last change to a preset or setting parameter, not
  again until the next change. Mute is in neither, so the outputs always start muted.

## Change from the plan

The plan (8a.5) said one sector, "erased only when full". With one sector, the erase before the
rewrite is a window in which a power cut loses every preset. Two sectors close it, at the cost of
another 128 KB of the M4's 1 MB bank (it needs little before batch 11). Decision-log row added.

## Test evidence (PC, simulated flash)

| Case | Result | Test |
|---|---|---|
| Power cut at every byte of a 928-byte record write | the slot holds the old preset, or the new one once all 904 content bytes are written; the store writes again after | `test_power_cut_at_every_byte_of_a_write` |
| Power cut at every 97th byte of a compaction, and during its erase | every slot keeps its last good value; the store recovers | `test_power_cut_during_compaction` |
| Several compactions, alternating sectors | every slot correct after a reboot | `test_full_sector_compacts_and_keeps_every_slot` |
| A flipped bit in the newest record; then in the older one as well | falls back to the older; then the slot is empty | `test_corrupted_record_falls_back_to_the_previous_one` |
| A hand-made older record: one known id, one unknown | known set, unknown ignored, the rest default | `test_older_record_with_fewer_and_unknown_parameters` |
| Power-on record timing, contents, mute not restored | written at 2.0 s, once | `test_power_on_record` |

**Found by the byte-by-byte test:** a cut inside the padding of a record's last flash word still
leaves a good record, because the padding is erased flash already. The first version of the test
expected the old preset there; the store was right.

## On the target

Not run: no board yet. To run: `ptime` on the console (time of one record write), then `preset
save`, power cycle, `preset list` and `preset load`. Plan item: the audio overrun counter stays 0
while 100 records are written (needs batch 2).

Target risks, each marked for the bench:
- A word torn by a power cut can fail its ECC check, and a load from it is a bus fault. The read
  path masks it (FAULTMASK with SCB CCR.BFHFNMIGN) and reports the double-error flag in
  FLASH_SR2 as a failed read, which the store treats as a bad record. Without that, a torn word
  would fault at every start-up. Shown on the board (2026-11-18, `tools/torn_write_test.py`):
  96 watchdog resets swept across a save, 32 start-ups met a torn record (up to 2 double and 2
  single ECC errors), none faulted, and slot 2 always held the old or the new record.
- FAULTMASK also holds off the audio interrupt, so reads go in 64-byte pieces.
- An erase blocks the main loop for up to about 2 s [Verify]; the audio interrupt keeps running,
  since the M7 executes from bank 1 [Verify, SPEC V17].
- The D-cache lines of a sector are invalidated after every erase and program.
- Endurance: about 100 records fit a sector, so one erase per 100 saves; at 10 000 cycles
  [Verify] that is a million saves.

## From the transcripts

No transcript covers flash storage (none is listed for batch 8a).

## Open questions

- The erase could run without blocking the main loop (start it, poll the flag); worth it only if
  the 2 s pause in the console is a problem in use.
