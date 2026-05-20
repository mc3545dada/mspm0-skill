# SDK Schema Lookup

Use this before authoring unfamiliar `.syscfg` fields or enum values.

There is no single friendly MSPM0 `.syscfg` field manual that lists every module field, enum, solver rule, and clock option. Treat `.syscfg` editing as evidence-based modification.

## Source Priority

Use sources in this order:

1. The user's existing `.syscfg`.
2. Packaged examples under `examples/`.
3. Local TI MSPM0 SDK `.syscfg` examples.
4. Local SDK module metadata under `source/ti/driverlib/.meta/*.syscfg.js`.
5. SysConfig GUI / standalone SysConfig output for the same device, package, SDK, and tool version.
6. Small scaffolds under `assets/snippets/`.

Do not invent device, package, product, board, or version metadata.

## Local SDK Locations

Search examples:

```text
<mspm0_sdk>/examples/**/*.syscfg
```

Inspect module definitions:

```text
<mspm0_sdk>/source/ti/driverlib/.meta/GPIO.syscfg.js
<mspm0_sdk>/source/ti/driverlib/.meta/UART.syscfg.js
<mspm0_sdk>/source/ti/driverlib/.meta/SYSCTL.syscfg.js
<mspm0_sdk>/source/ti/driverlib/.meta/PWM.syscfg.js
<mspm0_sdk>/source/ti/driverlib/.meta/TIMER.syscfg.js
<mspm0_sdk>/source/ti/driverlib/.meta/ADC12.syscfg.js
<mspm0_sdk>/source/ti/driverlib/.meta/DMA.syscfg.js
```

Use the helper:

```powershell
python scripts\index_syscfg_examples.py C:\ti\mspm0_sdk_2_10_00_04 --board LP_MSPM0G3507 --module UART
```

TI `LP_MSPM0G3507` examples are often useful for Tianmengxing MSPM0G3507 work, but board pin maps still need Tianmengxing verification.

## Validation

After editing `.syscfg`, run SysConfig CLI or rebuild. If validation cannot be run locally, say so directly:

```text
SysConfig validation was not completed.
```
