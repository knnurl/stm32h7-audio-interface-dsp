# The control protocol, version 1

Batch 8a. `ctl_proto`. This note is the specification; `CTL_PROTO_VERSION` in
`ctl/include/ctl/ctl_proto.h` is its version. A change that breaks a client raises the version.

## Transport

Line-based ASCII text, one command per line. Lines end with CR, LF or CR LF; a blank line gets
no reply. Input lines are at most 128 bytes; a longer one is answered `err 8` when it ends. The
UART console carries it now (115200 8N1, the ST-LINK virtual COM port); the USB serial port after
batch 4. The parser takes bytes in any split.

On the UART, the board's own commands (`info`, `cases`, `bench`, `vec`, `fault`, `ptime`) share
the line; everything else is the protocol. The self-test list command was renamed from `list` to
`cases` so `list` belongs to the protocol.

## Replies

Every command ends with exactly one line:

- `ok ...` on success, with the result;
- `err <code> <reason>` on failure.

`list` and `preset list` send data lines starting `= ` before it. Lines the device sends unasked
start with `#`. A client reads until `ok` or `err`, collecting `=` lines and setting `#` lines
aside.

| Code | Meaning |
|---|---|
| 1 | Syntax: wrong number of arguments (the reason gives the usage) |
| 2 | Unknown command (names are case-sensitive, lower case) |
| 3 | Unknown parameter |
| 4 | Bad value (not a number, not a slot, not a mode) |
| 5 | Knob wins: set the parameter's mode to pc first |
| 6 | Read-only (a meter) |
| 7 | Preset store failed, or the slot is empty |
| 8 | Line too long |
| 9 | The parameter has no knob |
| 10 | Budget: the effect slot and strip saturation cannot run together (`ctl_core.h`) |

## Commands

| Command | Reply |
|---|---|
| `hello` | `ok hello proto=1 fw=<version> unit=0x<8 hex> params=<n>` |
| `list` | per parameter `= <id> <name> <unit or -> <min> <max> <default> <lin/log/vol/step> <flags> <label>`, then `ok list <n>`. Flags: k knob, b button, p preset, s setting, r read-only, `-` none. The label is the rest of the line. |
| `get <name>` | `ok <name> <value>` |
| `set <name> <value>` | `ok <name> <value held>`: the value after clamping and rounding, so a client sees what it got |
| `mode <name> [knob\|pc]` | `ok mode <name> knob\|pc attached=0\|1` |
| `meters on\|off` | `ok meters on\|off`; when on, `# meters <name>=<value> ...` lines at about 30 Hz |
| `preset save <1-8> [name]` | `ok preset save <n>`. Without a name: `preset <n>`. Names: 16 bytes. |
| `preset load <1-8>` | `ok preset load <n> refused=<k>`: k knob parameters kept their knob's value |
| `preset name <1-8> <name>` | `ok preset name <n>` |
| `preset list` | per stored slot `= <n> seq=<sequence> <name>`, then `ok preset list <count>` |
| `src [inputs\|mix]` | `ok src inputs\|mix` (the record source) |
| `tempo [bpm]` | `ok tempo <stored bpm> source=stored`, or while MIDI clock leads `ok tempo <followed bpm> source=midi stored=<stored bpm>`; a value sets the stored tempo |
| `stat` | `ok stat lines= errors= refused= to_audio= coalesced= waiting= preset_writes= compactions= flash_errors= flash_free=` |

Unsolicited: `# set <name> <value>` for every change the PC did not make itself (a knob, a
button, MIDI, a preset recall), so a client's view stays current without polling.

## Numbers

Values are printed with up to four decimals, trailing zeros removed (`0.5`, `-12`, `20000`),
without the C library's printf, so the PC and the target print the same text. Input accepts
`[+-]digits[.digits][e[+-]digits]`; `nan`, `inf` and hex are refused.

## Robustness

| Measurement | Value | Test or command |
|---|---|---|
| Fuzz under the MSVC address sanitiser: random bytes, random lines of real words, random MIDI | 200 000 iterations, 12 MB, no report, 3.4 s | `test_fuzz_under_the_address_sanitiser` (`build/host/ctl/Release/ctl_fuzz.exe 200000 7`) |
| Every command and error | 25 cases | `test_commands` |
| Bytes split anywhere; mixed line endings | as one line | `test_split_anywhere` |

## From the transcripts

No transcript covers a control protocol (none is listed for batch 8a).

## Open questions

- A binary framing for the USB serial port (batch 4) would cut the meter traffic, but a person
  can no longer type it. Text stays unless the meter rate proves too much for full-speed USB.
- The console's own line reader cuts lines at 128 bytes rather than answering `err 8`; the
  USB transport will use `ctl_proto_feed`, which does answer.
