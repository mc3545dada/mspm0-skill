---
name: mspm0-ccs
description: Tool-neutral CLI agent rules for TI MSPM0 development with Code Composer Studio, Keil/uVision, CMake/GCC/OpenOCD, SysConfig, and DriverLib. Use when an agent needs to inspect or modify MSPM0 projects, edit .syscfg configuration, avoid generated SysConfig/build files, use DriverLib APIs, validate SysConfig output, package reusable MSPM0 examples, or work on NUEDC-style MSPM0 embedded firmware.
---

# MSPM0 Agent Skill

Use this skill for TI MSPM0 firmware projects that use SysConfig and DriverLib through CCS / CCS Theia, Keil/uVision, or CMake + Arm GNU Toolchain + OpenOCD workflows. It is intended for Claude Code, OpenCode, OpenClaw, Continue, Cursor, Codex, and similar CLI/editor agents.

## Default Workflow

1. Locate the project `.syscfg` or `system.syscfg`, editable source files, generated `ti_msp_dl_config.h`, and the active project entrypoint: `targetConfigs/*.ccxml` for CCS, `*.uvprojx` plus scatter file for Keil/uVision, or `CMakeLists.txt` plus OpenOCD `.cfg` files for CMake/GCC/OpenOCD.
2. Run `python scripts/check_syscfg.py <project-dir>` when this skill is available.
3. Read `.syscfg` metadata: device, package, SDK product, SysConfig version, modules, instances, pins, clocks, and interrupts.
4. Inspect generated `ti_msp_dl_config.h` for macro names, IRQ names, instance names, and the exact SysConfig init function spelling.
5. Before adding unfamiliar SysConfig fields, inspect the user's existing `.syscfg`, `examples/*/manifest.json`, TI SDK examples, or `source/ti/driverlib/.meta/*.syscfg.js`.
6. Modify the smallest relevant `.syscfg` and application-code surface.
7. Regenerate SysConfig output or rebuild through the active toolchain's generated build flow.
8. If flashing or debugging, confirm the configured probe backend matches the connected hardware and prefer a System Reset after programming.

## Core Rules

- Treat `.syscfg` as the source of truth for pinmux, peripheral setup, clocks, interrupts, DMA ownership, and generated initialization.
- Prefer SysConfig + DriverLib for GPIO, UART, PWM, Timer, ADC, I2C, SPI, DMA, and clock setup.
- Do not hand-edit generated outputs such as `Debug/ti_msp_dl_config.c`, `Debug/ti_msp_dl_config.h`, the project-root `ti_msp_dl_config.c` / `ti_msp_dl_config.h` pair in Keil layouts, `device_linker.cmd`, `Objects/`, `Listings/`, object files, maps, or `.out` files.
- Preserve `.syscfg` metadata such as `@cliArgs`, `@v2CliArgs`, `@versions`, `--device`, `--package`, and `--product`.
- Do not guess generated names. Read `ti_msp_dl_config.h` and use the local macros and the local init function spelling, such as `SYSCFG_DL_init()`.
- Do not invent SysConfig fields, enum values, device metadata, board names, package names, or tool versions. Validate against local examples, SDK metadata, or SysConfig CLI.
- Preserve unrelated user code, comments, copyright headers, project layout, and existing `.syscfg` settings. If a requested feature requires a larger rewrite, explain why before making it when possible.
- Do not change device, package, SDK, compiler, CCS version, board, or debug probe without user confirmation.
- If SysConfig emits warnings, report them separately from build/flash success. Do not call a warning-producing generation "clean".
- If hardware behavior is not verified on a connected board, say that validation stopped at source, SysConfig, or build level.

## Board-Specific Pin Caution

When the user explicitly says the board is LCKFB Tianmengxing MSPM0G3507:

- Avoid choosing A21/PA21, A23/PA23, A02/PA02, A18/PA18, A10/PA10, and A11/PA11 for ordinary user-requested pin assignments unless the user asks for those pins or the local project already deliberately uses them.
- If the user asks to drive or reuse one of those pins, remind them that the Tianmengxing documentation marks these as special pins and says they should not be used unless necessary.
- Do not silently move an existing project away from these pins. Explain the board caveat first, then ask or proceed according to the user's intent.

## Project Shape Checks

- Simple projects usually keep most logic in `main.c`, `empty.c`, or a small number of files. It is acceptable to make narrowly scoped edits there.
- Framework projects often have multiple source directories such as `app/`, `bsp/`, `components/`, `core/`, `drivers/`, `hal/`, `middleware/`, or `tasks/`. First identify ownership boundaries before adding peripherals or changing control logic.
- Do not assume every MSPM0 project is CCS-like or single-file. A framework project can still use CCS, Keil, or CMake/GCC/OpenOCD.
- For control code, confirm whether timing comes from a timer ISR, RTOS task delay, hardware PWM/ADC trigger chain, or a main-loop poll before changing periods or priorities.

## Keil Project Checks

- Treat `system.syscfg` and `ti_msp_dl_config.c` / `ti_msp_dl_config.h` as the configuration source surface for Keil-based MSPM0 projects that keep SysConfig outputs at the project root.
- Treat a Keil `.uvprojx` as the project entrypoint, the scatter file as the linker source of truth, and `Objects/`, `Listings/`, `*.uvoptx`, build logs, and generated outputs as inspection-only unless a request explicitly targets them.
- For a project's application code, follow its own source layout rather than assuming CCS defaults.

## CMake / GCC / OpenOCD Checks

- Treat `CMakeLists.txt`, toolchain files, and OpenOCD `.cfg` files as the project entrypoints for CMake/GCC/OpenOCD projects.
- Build through the existing CMake build directory when present, for example `cmake --build cmake-build-debug --target <target>`.
- MSPM0 OpenOCD flashing usually requires a TI MSPM0-capable OpenOCD build or TI extension branch. If OpenOCD reports `unable to find a matching CMSIS-DAP device`, report that as probe discovery failure rather than firmware failure.
- Do not require CCS `targetConfigs/*.ccxml` when the active project uses OpenOCD instead of DSLite.

## FreeRTOS Checks

- If `FreeRTOSConfig.h`, `FreeRTOS.h`, `task.h`, `xTaskCreate`, or `vTaskStartScheduler` are present, treat the project as RTOS-aware.
- Keep RTOS handling lightweight: respect existing task, queue, ISR, and blocking-call boundaries; do not impose a specific framework architecture unless the user asks.

## Ambiguous Requests

If the user omits important hardware parameters, do not silently choose risky values.

- For low-risk defaults, use this skill's `examples/` or local TI SDK examples, then tell the user which defaults were applied.
- For important parameters, ask before editing and offer a concrete recommendation.
- Important missing parameters include pin, peripheral instance, UART baud/data/parity/stop bits, Timer period, PWM frequency/duty/polarity, ADC channel/reference/sample time, DMA direction/source/destination, interrupt priority, and external-module power/logic levels.

Example: if the user asks "add a timer interrupt", ask which timer and period they want, and recommend a starter such as TIMG at 1 ms or 10 ms if they are unsure.

## External Modules And Hardware Debugging

When asked to drive an external module, sensor, motor driver, servo, display, radio, or custom board:

- Ask for the module datasheet, schematic, pin map, supply voltage, logic level, communication protocol, and key parameters when they are not available.
- Verify wiring assumptions before blaming code: power, ground, pull-ups, level shifting, reset/enable pins, boot pins, chip select, UART TX/RX crossover, I2C address, SPI mode, PWM polarity, and shared pins.
- If repeated attempts fail and SysConfig, build, flash, and code logic look correct, explicitly raise the possibility of wiring, power, module mode, datasheet mismatch, damaged hardware, or wrong test procedure.
- Separate "firmware looks correct" from "hardware proved correct".

## Reference Selection

Read references only when needed:

- `references/sysconfig_ccs_workflow.md`: `.syscfg` editing, CCS / Keil / CMake project layout, SysConfig CLI, gmake, CMake build, DSLite/J-Link, and OpenOCD.
- `references/driverlib_runtime_rules.md`: DriverLib usage, interrupts, clock tree, delays, and common runtime mistakes.
- `references/sdk_schema_lookup.md`: how to find official SysConfig fields and examples in the local MSPM0 SDK.
- `references/hardware_validation_notes.md`: verified Tianmengxing MSPM0G3507 lessons, HFXT warnings, flash/reset behavior, and real-board caveats.
- `references/ccs_dss_debug.md`: CCS Debug Server Scripting (`ccs-dss`) debug workflow, breakpoints, register reads, and current limitations.

Use `examples/` as one source for reusable tested patterns. Prefer `scripts/list_examples.py` to inspect available examples before opening individual example files, but do not assume packaged examples outrank the user's existing project structure or official TI SDK examples.

## Examples

Each reusable example should contain:

```text
examples/<name>/
├─ example.syscfg
├─ README.md
├─ manifest.json
└─ src/
   └─ source files copied from the minimal relevant project surface
```

Do not require users to drop full CCS projects into `examples/`. Use `scripts/capture_example.py` to extract a compact example package from a real project.

When applying an example to a user project:

- Treat skill examples as proven references, not mandatory project templates.
- Copy only the needed `.syscfg` fields, generated-name expectations, code pattern, or debugging lesson.
- Preserve the user's existing file layout and naming. If an example uses `BSP/`, do not create `BSP/` in the user project unless the user asked for that structure or the project already follows it.
- Prefer the user's local style when it conflicts with an example's directory names, wrapper names, or layering.
- Consider official TI SDK examples and local SDK metadata at the same or higher priority when they better match the user's board, SDK version, peripheral, or toolchain.
- For DMA UART examples, keep TX buffers per UART instance, avoid shared static printf buffers, and choose RX handling per port: ISR callback for the one port that needs immediate line parsing, `UART_poll()` for extra receive ports, or TX-only init for ports that do not receive.

## Tools

- `python scripts/check_syscfg.py <project-dir>`: static project check for `.syscfg`, generated files, pins, init spelling, project shape, CCS/Keil/CMake/OpenOCD clues, build output, target config, and validation hints.
- `python scripts/list_examples.py`: list packaged examples from `examples/*/manifest.json`.
- `python scripts/capture_example.py <project-dir> --name <example-name> --include <glob>`: package selected source files and `.syscfg` from a user project into `examples/<example-name>/`.
- `python scripts/index_syscfg_examples.py <mspm0-sdk-root> --board LP_MSPM0G3507 --module UART`: search local TI SDK examples and module metadata.
- `python scripts/serial_console.py --list`: list serial ports.
- `python scripts/ccs_dss_debug.py <project-dir> probe --leave-running`: connect through CCS Debug Server Scripting, read reset/register state, verify the configured `.ccxml` debug path, and continue the target before disconnecting.
- `python scripts/ccs_dss_debug.py <project-dir> load-symbols --symbol main`: load debug symbols from `.out` without programming flash.

For the verified CH340 setup, use `python scripts/serial_console.py -p COM6 -b 115200 --timestamp --duration 10` after closing other serial tools such as VOFA+.
For line-based MCU parsers, send one test frame and wait for the echo with `python scripts/serial_console.py -p COM6 -b 115200 --send "ping" --send-line --timestamp --duration 3`. Use `--send-hex "00 00 80 3F"` when testing binary payloads.

## Flash Backends

The verified CCS flash path is DSLite / UniFlash with J-Link. For automated flashing after clock-tree changes, prefer DSLite System Reset:

```text
dslite -c <target.ccxml> -e -r 2 -u <project.out>
```

For CMake/GCC/OpenOCD projects, use the project's existing flash target or explicit OpenOCD config. Keep the backend explicit and report probe-discovery errors separately from build success.

## Debug Backends

The currently packaged automated debug helper is the CCS Debug Server Scripting backend (`ccs-dss`):

```text
python scripts/ccs_dss_debug.py <project-dir> probe --leave-running
python scripts/ccs_dss_debug.py <project-dir> run-to-symbol --symbol main --load --reset "System Reset"
python scripts/ccs_dss_debug.py <project-dir> break-line --source BSP/UART.c --line 75 --symbols --reset "System Reset"
python scripts/ccs_dss_debug.py <project-dir> break-address --address 0x2564 --symbols --reset "System Reset"
```

Use it only for CCS / CCS Theia / UniFlash-style projects with a valid `targetConfigs/*.ccxml`. The physical probe is selected by `.ccxml`, so the backend is not inherently J-Link-only; it can also work with CCS-supported probes such as XDS110 when the project configuration matches the hardware.

Use `--symbols` or `load-symbols` when firmware is already flashed and the goal is to set breakpoints or inspect symbols without rewriting flash. Do not treat `ccs-dss` as the OpenOCD path. For CMake/GCC/OpenOCD projects, keep future debugging under a separate `openocd-gdb` backend. Debug actions can halt the CPU, so report that risk before using breakpoints or register inspection on real-time control hardware.
