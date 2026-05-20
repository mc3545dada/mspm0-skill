# Hardware Validation Notes

Use this for verified Tianmengxing MSPM0G3507 lessons and real-board caveats.

## Verified Environment

Validated combination:

- Board: LCKFB Tianmengxing MSPM0G3507
- IDE: CCS / CCS Theia
- SDK: MSPM0 SDK 2.10.00.04
- SysConfig: 1.26.2
- Compiler: TI Arm Clang 4.0.3 LTS
- Debug probe: J-Link through UniFlash / DSLite
- Validated peripherals: PB22 onboard LED, UART0 blocking TX, PB22 TIMG8 PWM breathing LED
- Validated clock: 80 MHz CPUCLK with MFCLK 4 MHz for UART work

Other boards, packages, SDK versions, CCS versions, probes, and pin maps may work, but they are not guaranteed by these notes.

## PB22 LED Lessons

The LCKFB Tianmengxing onboard LED uses PB22. A verified GPIO blink used generated names similar to:

```c
LED_PORT
LED_PIN_22_PIN
SYSCFG_DL_init()
```

The original LED blink was a 32 MHz baseline using `delay_cycles(32000000)`.

## 80 MHz Clock Tree Lessons

The verified 80 MHz pattern uses HFXT 40 MHz on PA5/PA6, SYSPLL, ULPCLK divider 2, and MFCLK gate enabled.

SysConfig can generate successfully while warning:

```text
HFXT peripheral.$assign: Solution may have changed
HFXT peripheral.hfxInPin.$assign: Solution may have changed
HFXT peripheral.hfxOutPin.$assign: Solution may have changed
```

Do not hide this. Confirm generated `CPUCLK_FREQ`, `GPIO_HFXIN_*`, and `GPIO_HFXOUT_*`, or ask the user to inspect the clock tree GUI.

## UART0 Blocking TX Lessons

The verified UART smoke test used UART0 at 115200 8N1 with PA10/PA11 and a CH340 PC adapter. Treat it as a blocking transmit baseline, not a final DMA or variable-length receive design.

## PWM Breathing LED Lessons

The verified PB22 PWM example used TIMG8 CCP1, a period of 1000 counts, and generated macro `GPIO_PWM_0_C1_IDX`.

Successful runtime pattern:

- set the first compare value before starting the timer
- update CCP1, not channel 0
- avoid exact compare boundaries `0` and `period`
- use `1..999` for a period of `1000`
- at 80 MHz, `delay_cycles(800000)` is roughly 10 ms per step

Failed patterns included one-second delay per brightness step and exact boundary values that made the LED appear off or glitchy.

## Flash And Reset

Manual load-and-run after a clock-tree change can behave differently from a full reset. A verified 80 MHz test blinked at about 2.5 seconds immediately after plain flash, then about one second after board reset. DSLite `-r 2 -u` made automated flashing start correctly.

If J-Link connection fails after a previous attempt, stale `DSLite`, `JLink`, or `JLinkGUIServer` processes may need to be closed before retrying.
