# SysConfig And CCS Workflow

Use this when editing `.syscfg`, validating a CCS project, building, or flashing.

## SysConfig Editing

Treat `.syscfg` as the editable source for device metadata, pinmux, peripheral instances, clocks, DMA, interrupts, and generated initialization.

Preserve metadata:

```text
@cliArgs
@v2CliArgs
@versions
--device
--package
--product
```

Keep the original metadata comment syntax valid. Some empty CCS projects use `//@cliArgs` line comments. Do not rewrite those as `* @cliArgs` unless the line is inside an active `/* ... */` block; a real failure from this mistake was `SyntaxError: Unexpected token '*'`.

Editing strategy:

1. Find an existing local instance or an example with the same device/package/peripheral.
2. Copy local style instead of inventing fields.
3. Change only the requested module, pin, clock, or runtime behavior.
4. Preserve `$suggestSolution` / `$assign` lines unless you know the solver impact.
5. Run SysConfig CLI or rebuild.
6. Inspect generated `ti_msp_dl_config.h` for names.

## CCS Project Rules

Editable surfaces are normally `.syscfg`, user source files, user headers, and project docs.

Generated or build outputs are inspection-only:

```text
Debug/ti_msp_dl_config.c
Debug/ti_msp_dl_config.h
Release/ti_msp_dl_config.c
Release/ti_msp_dl_config.h
Debug/device.opt
Debug/device_linker.cmd
Debug/device.cmd.genlibs
Debug/*.mk
*.o
*.d
*.out
*.map
```

Avoid unnecessary edits to `.project`, `.cproject`, `.ccsproject`, `.settings/`, and `targetConfigs/*.ccxml`. These files can change SDK discovery, compiler options, debug probe, and linker behavior.

## Validation Chain

Run the static checker first:

```powershell
python scripts\check_syscfg.py <project-dir>
```

Run SysConfig CLI when available. Prefer the exact command generated in `Debug/subdir_rules.mk` when it exists. A fresh project may not have generated makefiles yet; SysConfig CLI can still validate `.syscfg` into a temporary output directory.

Build through CCS-generated makefiles when present:

```powershell
gmake -C <project-dir>\Debug clean all
```

If `Debug/makefile` references both `../device_linker.cmd` and `-l"./device_linker.cmd"`, treat that as a CCS generated build-file state issue, not an application or SysConfig failure. Regenerate/rebuild in CCS when possible. For one-off CLI validation, avoid linking the same generated linker script twice.

## DSLite / J-Link Flash

The verified flash path is DSLite / UniFlash with J-Link:

```powershell
dslite -c <project-dir>\targetConfigs\MSPM0G3507.ccxml -N
dslite -c <project-dir>\targetConfigs\MSPM0G3507.ccxml -e -r 2 -u <project-dir>\Debug\<project>.out
```

The `.ccxml` must match the physical probe. A project configured for XDS110 can build successfully and still fail to flash through J-Link.

Use `-r 2 -u` for automated flashing after clock-tree changes. This performs a System Reset after programming. If manual flashing appears to start with the wrong clock speed, press the board reset button before judging the firmware.

If `dslite -N` hangs or cannot list the core, stop stale CCS/DSLite/J-Link sessions, reconnect if needed, and retry detection before erase/program operations.

## OpenOCD Placeholder

OpenOCD support is reserved for future backend work. Until a board/probe combination has been tested, do not claim OpenOCD flashing is supported. Future wrappers should keep the flash backend explicit, for example `--backend dslite` or `--backend openocd`.

## Hardware Claims

Report validation levels separately:

- source/static inspection
- SysConfig generation
- compile/link
- flash tool success
- physical board behavior
- serial/logic analyzer observation

Do not report hardware behavior as verified unless it was observed on connected hardware.
