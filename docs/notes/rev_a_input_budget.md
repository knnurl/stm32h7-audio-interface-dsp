**Do the exercise `docs/exercises/EX5_input_budget.md` before reading this file.**

# Rev A line input budget (batch 5, stage 2)

2026-11-18. Claude's worked budget for the circuit in EX5. Givens as stated there (SBAS452A 8.5,
SBOS855E; A-weighted noise bandwidth 12.47 kHz, sqrt = 111.7).

## 1. Values and level

- ADC full scale 0.4 x 5.0 = 2.0 V rms differential. +20 dBu = 7.746 V rms. Required gain
  2.0 / 7.746 = 0.2582 (-11.76 dB).
- **Rin = 20.0 k, Rf = 5.11 k** (E96): G = 0.2555, so **0 dBFS = +20.1 dBu**. Input impedance
  20 k per leg, 40 k differential.
- Headroom over +4 dBu: **16.1 dB**.
- Clipping: each leg swings 1.0 V rms (1.41 V peak) about 2.5 V at 0 dBFS; the op-amp reaches
  +11.2 V, 8.7 V above centre, 6.15 times: **15.8 dB above 0 dBFS**. The ADC clips first. The
  input TVS (15 V stand-off) sets the survivable level: about +29 dBu balanced.

## 2. Noise per leg at the ADC pin

| Source | Density | Gain | Out (nV/rtHz) |
|---|---|---|---|
| Rin 20 k | 18.15 | 0.2555 | 4.64 |
| Rf 5.11 k | 9.17 | 1 | 9.17 |
| OPA1678 e_n | 4.5 | 1.2555 | 5.65 |
| i_n, source 100 ohm, 47 ohm RC | | | under 0.4 |
| **Leg** | | | sqrt(137.5) = **11.73** |

VCOMAD's noise is common to both legs and rejected by the ADC's 80 dB CMRR.
Differential: 11.73 x sqrt(2) = 16.58 nV/rtHz; x 111.7 = **1.85 uV(A)**.

## 3. Totals

- ADC floor: 2.0 / 10^(107/20) = **8.93 uV(A)**.
- Total: sqrt(8.93^2 + 1.85^2) = **9.12 uV(A)**.
- **Dynamic range 20 log(2.0 / 9.12e-6) = 106.8 dB(A)**; the front end costs **0.2 dB**.
- Referred to the input: 9.12 / 0.2555 = 35.7 uV(A) = **-86.7 dBu(A)**.
- SNR at +4 dBu: **90.7 dB(A)**. Target DR 105 dB (SPEC 3.3): met.

## 4. Other 0 dBFS levels (Rin 20 k kept)

| 0 dBFS | Rf | DR | Input noise | SNR at +4 dBu | Headroom |
|---|---|---|---|---|---|
| +18 dBu | 6.49 k | 106.8 dB | -88.8 dBu(A) | 92.8 dB | 14 dB |
| **+20 dBu** | 5.11 k | 106.8 dB | -86.7 dBu(A) | 90.7 dB | 16 dB |
| +24 dBu | 3.24 k | 106.9 dB | -82.8 dBu(A) | 86.8 dB | 20 dB |

The ADC sets the floor, so each dB of headroom costs a dB of SNR at nominal level. +20 dBu is the
proposal: 16 dB of headroom for 2 dB of SNR against +18.

## 5. Common-mode rejection

A common-mode input Vc gives Vc x (G1 - G2) differentially; with each leg's gain set by Rf/Rin,
worst-case mismatch is about 2 x 2 x tolerance: **1 %: about 28 dB; 0.1 %: about 48 dB**
(typically better, the errors being random). Proposal: 0.1 % thin-film for Rin and Rf (four per
channel). A 10 mV ground difference then gives about 40 uV (-86 dBu), at the noise floor. A
laser-trimmed line receiver (about 90 dB) is the upgrade if batch 7 measures hum [Verify parts].

## 6. Unbalanced source

TS plug: the cold leg sees ground, so the hot leg alone carries the signal: 0 dBFS is reached at
+20 dBu on the hot leg (10.96 V peak, under the TVS stand-off). The noise is unchanged; the CMRR
no longer helps against the source's ground.

## 7. From the transcripts

#78: low-impedance resistors to keep Johnson noise down; ESD, RF filter, coupling capacitor,
high-value bias resistor before the op-amp. Taken, with numbers (section 2). Not taken: the
half-supply divider bias (VCOMAD serves). #142: nothing on the analogue input.
