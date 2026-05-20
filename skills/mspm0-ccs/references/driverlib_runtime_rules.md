# DriverLib Runtime Rules

Use this when changing C/C++ runtime code, interrupts, timing, clocks, or external-module behavior.

## Initialization And Generated Names

Application code must call the generated SysConfig init function before using generated peripherals. Do not guess the spelling; inspect `ti_msp_dl_config.h`.

Common spelling:

```c
SYSCFG_DL_init();
```

Use generated macros for instances, ports, pins, IRQ names, and channel indexes. Do not copy example-specific macro names into a project unless the local generated header defines them.

## DriverLib Ownership

Prefer DriverLib APIs such as:

```c
DL_GPIO_setPins(port, pin);
DL_GPIO_clearPins(port, pin);
DL_GPIO_togglePins(port, pin);
DL_UART_transmitDataBlocking(uart, byte);
DL_TimerG_startCounter(timer);
DL_TimerG_setCaptureCompareValue(timer, value, index);
```

Keep pinmux, peripheral initialization, clocks, DMA, and interrupts in `.syscfg` when possible. Use application code for runtime behavior.

Avoid direct register-level peripheral configuration unless the user requested it, DriverLib cannot express the operation, and the reason is documented.

## Interrupts

Interrupt handlers should:

- clear the relevant interrupt flag
- do minimal work
- record state for the main loop or task
- use `volatile` for variables shared with non-ISR code

Avoid long delays, blocking serial I/O, complex parsing, slow bus transactions, and heavy control logic inside ISRs.

## Clock And Delay Rules

For the verified Tianmengxing MSPM0G3507 80 MHz pattern:

- HFXT: 40 MHz on PA5 / PA6
- SYSPLL: enabled
- CPUCLK: 80 MHz
- ULPCLK divider: 2
- MFCLK: 4 MHz from SYSOSC_4M, useful for UART examples

`delay_cycles(n)` depends on CPUCLK:

- 32 MHz: `delay_cycles(32000000)` is roughly 1 s
- 80 MHz: `delay_cycles(80000000)` is roughly 1 s

Use timers for real timing and control loops. Treat `delay_cycles()` as a smoke-test convenience.

If `delay_cycles(80000000)` gives about 2.5 s, the program is likely running near 32 MHz. After flash, issue a System Reset or press the board reset button.

## Common Mistakes

- Editing `Debug/ti_msp_dl_config.*` instead of `.syscfg`.
- Removing SysConfig metadata.
- Guessing `SYSCFG_DL_Init()` when the local project declares `SYSCFG_DL_init()`.
- Assuming any package pin can serve any peripheral function.
- Renaming generated instances casually and breaking application code.
- Reinitializing by hand a peripheral already owned by SysConfig.
- Reporting SysConfig warnings as clean success.
- Rewriting unrelated user code or copyright headers.

## External Modules

For sensors, displays, motor drivers, servos, radios, or custom modules, collect the datasheet, schematic or wiring table, voltage levels, protocol, address/mode pins, reset/enable pins, and required timing before writing a driver.

If repeated firmware attempts fail but SysConfig, build, flash, and runtime logic appear correct, ask the user to verify wiring, power, ground, level shifting, module mode, address pins, chip select, UART TX/RX crossover, pull-ups, and test procedure.
