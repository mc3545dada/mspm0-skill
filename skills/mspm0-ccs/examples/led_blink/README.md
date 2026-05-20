# Tianmengxing PB22 LED Blink Example

Minimal reference for blinking the onboard LED on the LCKFB Tianmengxing MSPM0G3507 board.

This example is based on the validated workflow summarized in `../../references/hardware_validation_notes.md`. It is not a complete CCS import project. It is an agent-readable reference showing the `.syscfg` and C patterns that were verified on real hardware.

## Clock Note

This LED-only reference is the original 32 MHz baseline. Its `main.c` uses `delay_cycles(32000000)` for a rough one-second blink.

Later Tianmengxing work often uses 80 MHz CPUCLK. For 80 MHz examples, use `delay_cycles(80000000)` for the same rough one-second smoke test and see `../../references/hardware_validation_notes.md`.

## Files

- `example.syscfg`: PB22 GPIO output configuration pattern
- `src/main.c`: DriverLib application code using generated macros
- `manifest.json`: machine-readable summary for example selection

## Agent Notes

- Configure the LED pin in `.syscfg`.
- On the Tianmengxing MSPM0G3507 board, the onboard LED used by the LCKFB LED tutorial is PB22.
- Do not manually edit generated `ti_msp_dl_config.c` or `ti_msp_dl_config.h`.
- After changing `example.syscfg`, run SysConfig or rebuild the real CCS project.
- Confirm the generated init function and macro names in the local generated header.

## Expected Generated Names

The example expects generated names similar to:

```c
LED_PORT
LED_PIN_22_PIN
SYSCFG_DL_init()
```

Real projects may generate different names if `$name` or pin names are changed.
