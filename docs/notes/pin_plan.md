# Pin plan: rev A main board onto the Nucleo-H755ZI-Q

Batch 5, stage 2, 2026-11-18. Draft for the owner's sign-off. Batch 2's breakout wiring uses the
same SAI1 pins (PE3 to PE6), so this file serves both.

Sources: **UM2408 Rev 6** (Feb 2025): Table 19 (morpho pin assignment, p. 46-47), Table 17 and
Figure 17 (Zio, p. 36-41), Table 16 (solder bridges, p. 32-35), Table 13 (USB, p. 30-31), Table 14
(Ethernet, p. 31-32), Table 12 (USART3, p. 30), 7.6 (LEDs, p. 27), 7.7 (buttons, p. 28), Table 11
(external SMPS, p. 26), 7.4 (power, p. 18-23). **Alternate functions:** STM32CubeMX 6.15 database
(`STM32H755ZITx.xml`, `GPIO-STM32H747_gpio_v1_0_Modes.xml`, in STM32CubeIDE 1.19.0), which encodes
DS12919's alternate-function table. Cross-checked against the pinned HAL 1.11.5's AF macros
(`stm32h7xx_hal_gpio_ex.h`): `GPIO_AF6_SAI1`, `GPIO_AF4_I2C1`, `GPIO_AF4_I2C4`, `GPIO_AF1_TIM1`,
`GPIO_AF1_TIM2`, `GPIO_AF1_TIM16`, `GPIO_AF2_TIM3`, `GPIO_AF2_TIM4`, `GPIO_AF9_SPDIF`,
`GPIO_AF10_SAI2` and `GPIO_AF10_OTG2_FS` all agree (the HAL calls the PA11/PA12 core OTG2_FS;
CubeMX calls it USB_OTG_FS). I2S_CKIN on AF5 sits in the HAL's SPI/I2S AF5 group. DS12919 itself
(Rev 2, Feb 2023) could not be fetched on 2026-11-18 (st.com timed out five times), so every AF
number stays [Verify against DS12919], as does RM0399 for the S/PDIF output on SAI block A.

## 1. Mounting

The main board meets the Nucleo on **both morpho rows, CN11 and CN12** (2 x 35 each). Reason:
the Nucleo's only 5 V input suited to a 5 V rail, 5V_EXT, is on CN11 pin 6 only (UM2408 Table 6).
The morpho footprints are empty as shipped (7.17); male headers must be soldered in [owner's
go]. The Zio sockets stay unused.

## 2. Pins avoided, and why

| Pins | Reason | Source |
|---|---|---|
| PA1, PA2, PA7, PC1, PC4, PC5, PG11, PG13, PB13 | Ethernet RMII to the LAN8742A | Table 14 |
| PD8, PD9 | USART3 to the ST-LINK virtual COM port (our console) | Table 12 |
| PB0, PE1, PB14 | user LEDs LD1 to LD3 (firmware uses them) | 7.6 |
| PA13, PA14 | SWD | Table 19 note 4 |
| PB3 | SWO to the ST-LINK | Table 16 (SB49, SB50) |
| PC13, PA0 | user button B1 (PA0 through SB81/SB89) | 7.7, Table 16 |
| PH0, PH1, PC14, PC15 | HSE (ST-LINK MCO) and LSE | 7.9 |
| PG8, PG9, PG10, PG12 | external SMPS signals of CN6 | Table 11, Table 17 notes 2, 3, 12, 14 |
| PD10, PG7, PA8, PA10 | USB FS power enable (JP8), over-current (SB100), SOF/MCO1, ID | Table 13 |
| PB6, PB7 | alternative virtual COM port, Zio D0/D1 | Table 16 |
| BOOT0 (CN11-7) | recovery only: brought to an open 2-pin header on the main board | 7.4.8 |

Firmware note: the LAN8742A runs and drives its 50 MHz reference clock on PA1 unless put in
power-down through MDIO (BCR bit 11, UM2408 7.12 note 3). Batch 7 adds that to start-up.

## 3. The map

| Function | Pin | AF | Morpho pin | Zio (unused) | Checked against |
|---|---|---|---|---|---|
| SAI1_SCK_A, TDM bit clock (BCKAD and BCKDA tied) | PE5 | AF6 | CN11-50 | CN9-18 | Tables 17, 19 |
| SAI1_FS_A, frame (LRCKAD and LRCKDA tied) | PE4 | AF6 | CN11-48 | CN9-16 | Tables 17, 19 |
| SAI1_SD_A, to DIN1 (8 DAC slots) | PE6 | AF6 | CN11-62 | CN9-20, CN10-28 | Tables 17, 19; CN12-14 alternative is PA11 by default (motor-control SB10/SB22, Table 15) |
| SAI1_SD_B, from DOUT1 (6 ADC slots), synchronous | PE3 | AF6 | CN11-47 | CN9-22 | Tables 17, 19 |
| SAI1_MCLK_A (reserved, unused: the converter gets MCLK from the clock buffer) | PE2 | AF6 | CN11-46 | CN9-14 | |
| I2S_CKIN, SAI kernel clock from the oscillator buffer | PC9 | AF5 | CN12-1 | CN8-4 (SDMMC_D1, nothing fitted) | Tables 17, 19 |
| I2C1_SCL, codec control | PB8 | AF4 | CN12-3 | CN7-2 | Table 16 (SB62/SB39 to A4/A5 off by default) |
| I2C1_SDA | PB9 | AF4 | CN12-5 | CN7-4 | as above |
| CODEC_RST_n (pull-down) | PD3 | GPIO | CN11-40 | CN9-10 | |
| CODEC_OVF (reset done, ADC overflow), input | PE12 | GPIO | CN12-49 | CN10-26 | |
| OSC_SEL: 24.576 MHz OE and mux select (pull-up) | PD5 | GPIO | CN11-41 | CN9-6 | |
| OSC_22M_EN: 22.5792 MHz OE (pull-down) | PD6 | GPIO | CN11-43 | CN9-4 | |
| RAILS_OK, input, EXTI4 | PD4 | GPIO | CN11-39 | CN9-8 | |
| MUTE_MON: monitor relay driver (pull-down) | PE7 | GPIO | CN12-44 | CN10-20 | |
| MUTE_LINE34: line 3/4 relay driver (pull-down) | PE8 | GPIO | CN12-40 | CN10-18 | CN12-30 alternative (SB47/SB43) not used |
| HP_EN: OPA1622 enable (pull-down) | PE10 | GPIO | CN12-47 | CN10-24 | |
| POT1 bass | PA3 | ADC1_INP15 | CN12-37 | CN9-1 (A0) | |
| POT2 mid | PC0 | ADC1_INP10 | CN11-38 | CN9-3 (A1) | |
| POT3 treble | PA4 | ADC1_INP18 | CN11-32 | CN7-17 | CN12-29 alternative is PB5 by default |
| POT4 monitor | PA5 | ADC1_INP19 | CN12-11 | CN7-10 | LD1 alternative (SB65) off by default |
| POT5 phones | PA6 | ADC1_INP3 | CN12-13 | CN7-12 | |
| POT6 FX amount | PB1 | ADC1_INP5 | CN12-24 | CN9-7 (A3) | |
| POT7 blend | PF11 | ADC1_INP2 | CN12-62 | CN9-11 (A5, SB69/SB40) | |
| POT_REF (VREF+ = VDDA = VDD through R40) | VREFP | | CN12-7 | CN7-6 | Table 16 (R40) |
| POT_GND | AGND | | CN12-32 | | |
| LED1 to LED4 (TIM1_CH1 to CH4, PWM, sink) | PE9, PE11, PE13, PE14 | AF1 | CN12-52, 56, 55, 51 | CN9-15, CN10-6, 10, 8 | |
| LED5, LED6 (TIM2_CH3, CH4) | PB10, PB11 | AF1 | CN12-25, 18 | CN10-32, 34 | |
| LED7 (TIM16_CH1) | PF6 | AF1 | CN11-9 | CN10-5 (A6, SB73) | |
| ENC1 A, B (TIM3_CH1, CH2, encoder mode) | PC6, PC7 | AF2 | CN12-4, 19 | CN7-1, 11 | |
| ENC2 A, B (TIM4_CH1, CH2) | PD12, PD13 | AF2 | CN12-43, 41 | CN10-21, 19 | |
| ENC1_SW, ENC2_SW | PD2, PG14 | GPIO | CN11-4, CN12-61 | CN8-12, CN10-12 | |
| BTN1 to BTN5 (polled by `ctl_button`; EXTI lines 0, 1, 10, 11, 12 if wanted) | PD0, PD1, PC10, PC11, PC12 | GPIO | CN11-57, 55, 1, 2, 3 | CN9-25, 27, CN8-6, 8, 10 | |
| I2C4_SCL, SDA (OLED, batch 11) | PF14, PF15 | AF4 | CN12-50, 60 | CN9-19, 21 | |
| SPDIFRX1_IN0 (optical in, batch 10) | PD7 | AF9 | CN11-45 | CN9-2 | the other SPDIFRX inputs sit on RMII, VCP or SMPS pins |
| SAI2_SD_A in S/PDIF mode (optical out, batch 10) | PD11 | AF10 | CN12-45 | CN10-27 | [Verify RM0399: S/PDIF output on block A] |
| USB OTG_FS D- | PA11 | AF10 | CN12-14 | | Table 13, Table 16 (SB27); [Verify CN12-14 carries PA11 as shipped] |
| USB OTG_FS D+ | PA12 | AF10 | CN12-12 | | Table 13, Table 16 (SB26); [Verify CN12-12 "PA12 or NC"] |
| VBUS_DET (divider from the USB-C VBUS), EXTI15 | PE15 | GPIO | CN12-53 | CN10-30 | PA9 left to CN13's circuit (SB21) |
| 5V_EXT in (JP2 on 5-6) | | | CN11-6 | | Table 6 |
| 3V3 out to the panel | | | CN11-16 | | 7.4.7 |
| GND | | | CN11-8, 19, 20, 22, 49, 60; CN12-9, 20, 39, 54, 63 | | Table 19 |
| BOOT0 to a recovery header | | | CN11-7 | | 7.4.8 |

Peripherals used: SAI1, SAI2 (later), I2C1, I2C4, ADC1, TIM1, TIM2, TIM3, TIM4, TIM16, OTG_FS,
SPDIFRX (later), USART3 (console, unchanged). Free for firmware: TIM5 to TIM8, TIM12 to TIM15,
TIM17, LPTIMs. The firmware today uses only USART3 (grep of `fw/`).

## 4. Not finished yet

- Every AF number against DS12919's table (CubeMX and the HAL agree; the datasheet was not
  reachable); the per-pin and total GPIO current limits for the LED sinks; the FT (5 V tolerant)
  status of PE15 with VDD off; RM0399 for S/PDIF on SAI2 block A.
- The two CN12 USB pins by continuity on the owner's board.
- 96 kHz on rev B needs DOUT2/DIN2 (SBAS452A Table 11): no pins reserved on rev A (test pads only).

## 5. From the transcripts

#78: the pin-out was found with STM32CubeIDE and refined during layout; colour-coded nets for
sections. Taken: the CubeMX database as the pin source, groups by zone. #142: I2C for codec
control with address straps and a reset GPIO held low by a pull-down: taken (PB8/PB9, PD3).
Not taken: #78's single-bus sharing of I2C between the codec and other parts (the OLED gets its
own I2C4 so the ribbon stays off the codec's bus).
