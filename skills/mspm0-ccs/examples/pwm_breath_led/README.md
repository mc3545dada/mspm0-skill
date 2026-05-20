# PWM Breathing LED Example

Minimal reference for driving the LCKFB Tianmengxing MSPM0G3507 onboard PB22 LED with PWM.

This example is based on the verified `26testproject5` smoke test. It is not a complete CCS import project. It is an agent-readable reference showing the `.syscfg` and C patterns that were validated on real hardware.

## Clock Note

This example uses the 80 MHz clock-tree pattern summarized in `../../references/hardware_validation_notes.md`:

- CPUCLK: 80 MHz
- HFXT: 40 MHz input on PA5 / PA6
- SYSPLL: enabled
- ULPCLK divider: 2
- MFCLK gate: enabled

This differs from the older `empty_project` and `led_blink` examples, which are 32 MHz baseline examples.

## PWM Setup

- PWM module: `/ti/driverlib/PWM`
- Timer instance: TIMG8
- Output channel: CCP1
- Output pin: PB22
- Generated macro: `GPIO_PWM_0_C1_IDX`
- PWM period: 1000 timer counts
- PWM clock frequency observed: 2.5 MHz

The verified generated header contained:

```c
#define PWM_0_INST             TIMG8
#define PWM_0_INST_CLK_FREQ    2500000
#define GPIO_PWM_0_C1_PIN      DL_GPIO_PIN_22
#define GPIO_PWM_0_C1_IOMUX    (IOMUX_PINCM50)
#define GPIO_PWM_0_C1_IDX      DL_TIMER_CC_1_INDEX
```

## Files

- `example.syscfg`: 80 MHz clock tree and PB22 / TIMG8_CCP1 PWM setup
- `src/main.c`: DriverLib PWM breathing pattern
- `manifest.json`: machine-readable summary for example selection

## Application Pattern

The successful breathing pattern:

- Sets the first compare value before starting the timer.
- Updates `GPIO_PWM_0_C1_IDX`, not channel 0.
- Avoids compare values exactly equal to `0` and `period`.
- Uses about 100 steps per half-cycle.
- Uses `delay_cycles(800000)` at 80 MHz, about 10 ms per step.

Observed behavior:

- About 1 second from bright to dim.
- About 1 second from dim to bright.

## Failed Attempts

Initial slow version:

```c
#define STEP_SIZE  100
#define DELAY_CYC  80000000
```

This produced a very slow fade because each brightness step waited about one second.

Second attempt:

```c
for (int duty = 0; duty <= 1000; duty += 5)
```

This could make the LED appear off or glitchy on the verified board. Avoid the exact `0` and `period` boundaries for this smoke test.

## Build And Flash Notes

`gmake clean all` exposed a generated CCS makefile issue in one test project: `Debug/makefile` included `../device_linker.cmd` even though SysConfig generated `Debug/device_linker.cmd`.

That is a CCS project/build-file state issue, not a PWM SysConfig failure. Do not patch generated makefiles as the default fix. Regenerate the CCS build files, rebuild in CCS, or use the clean generated linker input path when doing a one-off CLI validation.

For automated flashing after 80 MHz clock-tree changes, use DSLite System Reset:

```powershell
dslite.bat -c path\to\MSPM0G3507.ccxml -e -r 2 -u path\to\project.out
```

If DSLite can enumerate the J-Link core but cannot connect to the target, close stale debug sessions or stop stale `DSLite` / `JLink` / `JLinkGUIServer` processes, then retry.
