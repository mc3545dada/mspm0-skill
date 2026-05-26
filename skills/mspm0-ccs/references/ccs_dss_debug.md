# CCS-DSS Debug Backend

Use this reference when the user asks the agent to debug a connected MSPM0 board through CCS / CCS Theia tooling.

This is the CCS Debug Server Scripting backend, abbreviated as `ccs-dss` in this skill. It is separate from an OpenOCD + GDB workflow. Do not apply these commands to a CMake/OpenOCD project unless that project also has a valid CCS `.ccxml` and the user explicitly wants to use CCS DSS.

## Scope

- Requires TI CCS / CCS Theia or UniFlash scripting components.
- Requires a valid `targetConfigs/*.ccxml` for the active board and probe.
- Requires a built CCS `.out` file when loading or reloading firmware.
- Uses the debug probe selected inside `.ccxml`, so it is not limited to J-Link. It can also work with CCS-supported probes such as XDS110 when the `.ccxml` matches the connected hardware.
- Does not cover OpenOCD/GDB debugging. Keep that as a future `openocd-gdb` backend.

## Safety Rules

- Debug actions can halt the CPU and disturb real-time behavior. Warn the user before halting a motor, power stage, or time-sensitive control loop.
- Prefer UART logging, logic analyzer capture, or scoped register reads when non-intrusive observation is enough.
- Use symbol breakpoints before source-line breakpoints when possible. Source-line breakpoints require valid debug info and a line that maps to generated code.
- If a source-line breakpoint fails but symbol breakpoints work, treat it as a debug-info/source-line mapping issue first, not proof that the board or probe failed.
- If connect/list-core operations hang, close stale CCS, DSLite, UniFlash, J-Link, or debug-server processes before retrying.

## Script

From this skill package:

```powershell
python scripts\ccs_dss_debug.py <project-dir> probe --leave-running
```

When running from the repository root:

```powershell
python skills\mspm0-ccs\scripts\ccs_dss_debug.py <project-dir> probe --leave-running
```

Common commands:

```powershell
# Connect, read reset types and registers, then continue the target before disconnecting.
python scripts\ccs_dss_debug.py <project-dir> probe --leave-running

# Program the current Debug/Release .out and use System Reset after loading.
python scripts\ccs_dss_debug.py <project-dir> load --reset "System Reset" --leave-running

# Program, reset, and halt at main.
python scripts\ccs_dss_debug.py <project-dir> run-to-symbol --symbol main --load --reset "System Reset"

# Program, reset, and halt at a source line.
python scripts\ccs_dss_debug.py <project-dir> break-line --source empty.c --line 5 --load --reset "System Reset"

# Load debug symbols only; do not program flash.
python scripts\ccs_dss_debug.py <project-dir> load-symbols --symbol main --symbol UART0TxDMADone

# Load symbols only, reset, and halt at a source line without reprogramming flash.
python scripts\ccs_dss_debug.py <project-dir> break-line --source BSP/UART.c --line 75 --symbols --reset "System Reset"

# Load symbols only, reset, and halt at an address breakpoint.
python scripts\ccs_dss_debug.py <project-dir> break-address --address 0x2564 --symbols --reset "System Reset"

# Continue a currently connected target and disconnect the debug session.
python scripts\ccs_dss_debug.py <project-dir> run

# Halt and print PC/SP/LR.
python scripts\ccs_dss_debug.py <project-dir> halt
```

Useful options:

- `--ccs-run <path>`: explicit CCS scripting `run.bat`.
- `--ccxml <path>`: explicit target configuration.
- `--out <path>`: explicit program output file.
- `--timeout-ms <n>`: DSS script timeout.
- `--keep-js`: keep the temporary JavaScript for diagnosis.
- `--symbols`: load debug symbols from `.out` without programming flash for commands that support it.
- `--leave-running`: remove breakpoints and continue target execution before disconnecting, where supported by the chosen command.

## Verified Notes

Validated on LCKFB Tianmengxing MSPM0G3507 + CCS / CCS Theia + J-Link with a CCS project containing `targetConfigs/MSPM0G3507.ccxml` and `Debug/<project>.out`.

Observed working operations:

- `ds.configure(ccxml)` and `ds.openSession(/cortex|m0|MSPM0/i)`.
- `session.target.connect()`.
- `session.target.getResets()` returning reset types including Board Reset, CPU Reset, Core Reset, and System Reset.
- `session.registers.read("PC")`, `SP`, and `LR`.
- `session.memory.loadProgram(<project>.out)`.
- `session.symbols.load(<project>.out)` for no-flash symbol loading.
- `session.symbols.getAddress(<symbol>)` and `session.symbols.lookupSymbols(<address>)`.
- Symbol breakpoint at `main`.
- System Reset followed by `target.run()` halting at `main`.
- Source-line breakpoint at a line with generated code.
- Address breakpoint at a known function address.
- `target.run(false)` to leave the target running before disconnect.

One tested source line failed because no code was associated with that exact line. Another source line in the same file worked. For agents, that means source-line breakpoint failure should be reported precisely and retried with a symbol, nearby executable line, or address.

For non-invasive diagnosis after firmware has already been flashed, prefer `load-symbols`, `break-line --symbols`, or `break-address --symbols` over `--load`. These commands load debug information from the `.out` file without rewriting flash.

## When To Stop

Stop and ask the user before continuing if:

- The `.ccxml` probe does not match the connected hardware.
- The board controls motors, high-power outputs, or moving mechanisms and the next step will halt the CPU.
- The script can connect but loading a new `.out` would overwrite firmware the user did not ask to replace.
- OpenOCD files are present and the user appears to be using an OpenOCD workflow instead of CCS DSS.
