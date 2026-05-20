# Empty CCS Project Baseline

Minimal reference captured from a newly created MSPM0G3507 CCS / CCS Theia empty project before the first build.

This is useful for agents because a fresh project may not yet have generated `Debug/ti_msp_dl_config.c` or `Debug/ti_msp_dl_config.h`. In that state, the agent can still inspect `empty.syscfg` and application source, but it cannot confirm generated macro names until SysConfig or CCS build runs.

## Clock Note

This is a fresh-project baseline and should be treated as the default 32 MHz-style configuration. It does not include the later validated 80 MHz HFXT / SYSPLL clock-tree setup.

In real Tianmengxing projects, 80 MHz is common. Use `../../references/hardware_validation_notes.md` and `../uart_blocking_tx/` when you need the verified 80 MHz pattern.

## Files

- `empty.syscfg`: initial SYSCTL + Board configuration
- `src/empty.c`: initial application loop calling `SYSCFG_DL_init()`
- `manifest.json`: machine-readable summary for example selection

Do not treat this as a complete importable CCS project. It is a small reference snapshot.
