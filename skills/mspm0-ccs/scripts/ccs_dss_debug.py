#!/usr/bin/env python3
"""Small CCS Debug Server Scripting wrapper for MSPM0 projects.

This tool targets the CCS/CCS Theia Debug Server Scripting path. It uses the
project's targetConfigs/*.ccxml, so the probe type comes from CCS project
configuration rather than this script.
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path


DEFAULT_RUN_BAT_CANDIDATES = (
    r"C:\ti\ccs2020\ccs\scripting\run.bat",
    r"C:\ti\uniflash_9.2.0\deskdb\content\TICloudAgent\win\scripting\run.bat",
)


def q(value: str | Path) -> str:
    return json.dumps(str(value).replace("\\", "/"))


def int_auto(value: str) -> int:
    return int(value, 0)


def find_first(paths: list[Path], what: str) -> Path:
    existing = [p for p in paths if p.exists()]
    if not existing:
        raise SystemExit(f"error: could not find {what}")
    return existing[0]


def find_run_bat(explicit: str | None) -> Path:
    if explicit:
        return find_first([Path(explicit)], "CCS scripting run.bat")

    env_candidates = [
        os.environ.get("CCS_DSS_RUN"),
        os.environ.get("CCS_SCRIPTING_RUN"),
    ]
    candidates = [Path(p) for p in env_candidates if p]
    candidates.extend(Path(p) for p in DEFAULT_RUN_BAT_CANDIDATES)

    ti_root = Path(r"C:\ti")
    if ti_root.exists():
        candidates.extend(sorted(ti_root.glob("ccs*/ccs/scripting/run.bat"), reverse=True))
        candidates.extend(
            sorted(
                ti_root.glob("uniflash*/deskdb/content/TICloudAgent/win/scripting/run.bat"),
                reverse=True,
            )
        )

    return find_first(candidates, "CCS scripting run.bat")


def find_ccxml(project_dir: Path, explicit: str | None) -> Path:
    if explicit:
        return find_first([Path(explicit)], "target .ccxml")
    preferred = sorted((project_dir / "targetConfigs").glob("*.ccxml"))
    fallback = sorted(project_dir.rglob("*.ccxml"))
    return find_first(preferred + fallback, "target .ccxml")


def find_program(project_dir: Path, explicit: str | None, required: bool) -> Path | None:
    if explicit:
        return find_first([Path(explicit)], "program output")
    candidates: list[Path] = []
    for build_dir in ("Debug", "Release"):
        candidates.extend(sorted((project_dir / build_dir).glob("*.out")))
    candidates.extend(sorted(project_dir.rglob("*.out")))
    if candidates:
        return candidates[0]
    if required:
        raise SystemExit("error: could not find program output (*.out)")
    return None


def js_prelude(timeout_ms: int, ccxml: Path) -> str:
    return f"""
function emit(obj) {{
  console.log(JSON.stringify(obj));
}}
function printable(value) {{
  if (typeof value === "bigint") return "0x" + value.toString(16);
  if (typeof value === "number") return "0x" + value.toString(16);
  return String(value);
}}
function readReg(session, name) {{
  try {{ return printable(session.registers.read(name)); }}
  catch (err) {{ return "ERR:" + String(err); }}
}}
function configureDebugServer(ds, ccxml) {{
  try {{
    ds.configure(ccxml);
    return "configure";
  }} catch (err1) {{
    ds.setConfig(ccxml);
    return "setConfig";
  }}
}}
function resetTarget(session, resetType) {{
  if (resetType) {{
    session.target.reset(resetType);
    emit({{event:"reset", type:resetType}});
  }} else {{
    session.target.reset();
    emit({{event:"reset", type:"default"}});
  }}
}}

var ds = initScripting();
ds.setScriptingTimeout({timeout_ms});
var ccxml = {q(ccxml)};
var session = null;
emit({{event:"ccs_dss_backend", backend:"ccs-dss", ccxml:ccxml}});
try {{
  var configureMethod = configureDebugServer(ds, ccxml);
  emit({{event:"configured", method:configureMethod}});
  session = ds.openSession(/cortex|m0|MSPM0/i);
  session.target.connect();
  emit({{event:"connected", isConnected:session.target.isConnected(), isHalted:session.target.isHalted()}});
"""


def js_finally(leave_running: bool = False) -> str:
    leave = ""
    if leave_running:
        leave = """
  try {
    session.breakpoints.removeAll();
  } catch (err) {}
  try {
    session.target.run(false);
    emit({event:"left_target_running"});
  } catch (err) {
    emit({event:"run_error", error:String(err)});
    throw err;
  }
"""
    return f"""
{leave}
}} catch (err) {{
  emit({{event:"error", error:String(err), stack:String(err.stack || "")}});
  throw err;
}} finally {{
  if (session) {{
    try {{
      session.target.disconnect();
      emit({{event:"disconnected"}});
    }} catch (err) {{
      emit({{event:"disconnect_error", error:String(err)}});
    }}
  }}
  ds.shutdown();
}}
"""


def make_probe_js(timeout_ms: int, ccxml: Path, leave_running: bool) -> str:
    return (
        js_prelude(timeout_ms, ccxml)
        + """
  var resets = {};
  try { resets = session.target.getResets(); }
  catch (err) { resets = {error:String(err)}; }
  emit({event:"resets", resets:resets});
  emit({event:"registers", pc:readReg(session, "PC"), sp:readReg(session, "SP"), lr:readReg(session, "LR")});
  try {
    session.target.halt();
    emit({event:"halted", isHalted:session.target.isHalted()});
  } catch (err) {
    emit({event:"halt_error", error:String(err)});
  }
"""
        + js_finally(leave_running=leave_running)
    )


def make_load_js(timeout_ms: int, ccxml: Path, program: Path, reset: str | None, leave_running: bool) -> str:
    reset_js = f"  resetTarget(session, {q(reset)});\n" if reset else ""
    return (
        js_prelude(timeout_ms, ccxml)
        + f"""
  var program = {q(program)};
  session.memory.loadProgram(program);
  emit({{event:"program_loaded", program:program}});
{reset_js}
"""
        + js_finally(leave_running=leave_running)
    )


def make_run_to_symbol_js(
    timeout_ms: int,
    ccxml: Path,
    program: Path | None,
    symbols: bool,
    symbol: str,
    reset: str | None,
    leave_running: bool,
) -> str:
    load_js = ""
    if program and not symbols:
        load_js = f"""
  var program = {q(program)};
  session.memory.loadProgram(program);
  emit({{event:"program_loaded", program:program}});
"""
    elif symbols and program:
        load_js = f"""
  var program = {q(program)};
  session.symbols.load(program);
  emit({{event:"symbols_loaded", program:program}});
"""
    return (
        js_prelude(timeout_ms, ccxml)
        + load_js
        + f"""
  try {{ session.breakpoints.removeAll(); }} catch (err) {{}}
  var symbol = {q(symbol)};
  var expected = session.expressions.evaluate(symbol);
  var bp = session.breakpoints.add(symbol);
  emit({{event:"breakpoint_added", type:"symbol", symbol:symbol, address:printable(expected), id:String(bp)}});
  resetTarget(session, {q(reset)});
  session.target.run();
  emit({{event:"halted_at_breakpoint", symbol:symbol, pc:readReg(session, "PC"), expected:printable(expected), halted:session.target.isHalted()}});
"""
        + js_finally(leave_running=leave_running)
    )


def make_break_line_js(
    timeout_ms: int,
    ccxml: Path,
    program: Path | None,
    symbols: bool,
    source: str,
    line: int,
    reset: str | None,
    leave_running: bool,
) -> str:
    load_js = ""
    if program and not symbols:
        load_js = f"""
  var program = {q(program)};
  session.memory.loadProgram(program);
  emit({{event:"program_loaded", program:program}});
"""
    elif symbols and program:
        load_js = f"""
  var program = {q(program)};
  session.symbols.load(program);
  emit({{event:"symbols_loaded", program:program}});
"""
    return (
        js_prelude(timeout_ms, ccxml)
        + load_js
        + f"""
  try {{ session.breakpoints.removeAll(); }} catch (err) {{}}
  var source = {q(source)};
  var line = {line};
  var bp = session.breakpoints.add(source, line);
  var location = "";
  try {{ location = String(session.breakpoints.getProperty(bp, "Hardware Configuration.Location")); }}
  catch (err) {{ location = "unknown"; }}
  emit({{event:"breakpoint_added", type:"line", source:source, line:line, location:location, id:String(bp)}});
  resetTarget(session, {q(reset)});
  session.target.run();
  emit({{event:"halted_at_breakpoint", source:source, line:line, pc:readReg(session, "PC"), sp:readReg(session, "SP"), lr:readReg(session, "LR"), halted:session.target.isHalted()}});
"""
        + js_finally(leave_running=leave_running)
    )


def make_load_symbols_js(
    timeout_ms: int,
    ccxml: Path,
    program: Path,
    symbols: list[str],
    lookup_address: str | None,
    lookup_length: int | None,
    leave_running: bool,
) -> str:
    symbol_lines = ""
    for symbol in symbols:
        symbol_lines += f"""
  try {{
    emit({{event:"symbol", symbol:{q(symbol)}, address:printable(session.symbols.getAddress({q(symbol)}))}});
  }} catch (err) {{
    emit({{event:"symbol_error", symbol:{q(symbol)}, error:String(err)}});
  }}
"""
    lookup_js = ""
    if lookup_address:
        length_arg = "" if lookup_length is None else f", {lookup_length}"
        lookup_js = f"""
  try {{
    var lookupAddress = Number({q(lookup_address)});
    emit({{event:"lookup_symbols", address:printable(lookupAddress), symbols:session.symbols.lookupSymbols(lookupAddress{length_arg})}});
  }} catch (err) {{
    emit({{event:"lookup_symbols_error", address:{q(lookup_address)}, error:String(err)}});
  }}
"""
    return (
        js_prelude(timeout_ms, ccxml)
        + f"""
  var program = {q(program)};
  session.symbols.load(program);
  emit({{event:"symbols_loaded", program:program}});
"""
        + symbol_lines
        + lookup_js
        + js_finally(leave_running=leave_running)
    )


def make_break_address_js(
    timeout_ms: int,
    ccxml: Path,
    program: Path | None,
    address: str,
    reset: str | None,
    leave_running: bool,
) -> str:
    load_js = ""
    if program:
        load_js = f"""
  var program = {q(program)};
  session.symbols.load(program);
  emit({{event:"symbols_loaded", program:program}});
"""
    return (
        js_prelude(timeout_ms, ccxml)
        + load_js
        + f"""
  try {{ session.breakpoints.removeAll(); }} catch (err) {{}}
  var addressText = {q(address)};
  var address = Number(addressText);
  var bp = session.breakpoints.add(address);
  var names = [];
  try {{ names = session.symbols.lookupSymbols(address); }} catch (err) {{}}
  emit({{event:"breakpoint_added", type:"address", address:printable(address), symbols:names, id:String(bp)}});
  resetTarget(session, {q(reset)});
  session.target.run();
  emit({{event:"halted_at_breakpoint", address:printable(address), pc:readReg(session, "PC"), sp:readReg(session, "SP"), lr:readReg(session, "LR"), halted:session.target.isHalted()}});
"""
        + js_finally(leave_running=leave_running)
    )


def make_halt_js(timeout_ms: int, ccxml: Path) -> str:
    return (
        js_prelude(timeout_ms, ccxml)
        + """
  session.target.halt();
  emit({event:"halted", pc:readReg(session, "PC"), sp:readReg(session, "SP"), lr:readReg(session, "LR"), halted:session.target.isHalted()});
"""
        + js_finally()
    )


def make_run_js(timeout_ms: int, ccxml: Path) -> str:
    return (
        js_prelude(timeout_ms, ccxml)
        + """
  session.target.run(false);
  emit({event:"left_target_running"});
"""
        + js_finally()
    )


def run_js(run_bat: Path, js_text: str, keep_js: bool, process_timeout_ms: int | None) -> int:
    temp_path: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(
            "w", suffix=".js", prefix="mspm0_ccs_dss_", encoding="utf-8", delete=False
        ) as temp:
            temp.write(js_text)
            temp_path = Path(temp.name)
        if keep_js:
            print(json.dumps({"event": "script_file", "path": str(temp_path)}), flush=True)
        timeout_s = None if process_timeout_ms is None else process_timeout_ms / 1000
        command = [str(run_bat), str(temp_path)]
        if os.name == "nt":
            command = ["cmd", "/d", "/c", str(run_bat), str(temp_path)]
        try:
            result = subprocess.run(command, text=True, timeout=timeout_s)
        except subprocess.TimeoutExpired:
            print(
                json.dumps({"event": "process_timeout", "timeout_ms": process_timeout_ms, "script": str(temp_path)}),
                flush=True,
            )
            return 124
        return result.returncode
    finally:
        if temp_path and not keep_js:
            try:
                temp_path.unlink()
            except OSError:
                pass


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="CCS-DSS debug helper for MSPM0 projects. This is not an OpenOCD/GDB backend."
    )
    parser.add_argument("project_dir", help="MSPM0 project directory")
    parser.add_argument("--ccs-run", help="Path to CCS scripting run.bat")
    parser.add_argument("--ccxml", help="Path to target .ccxml")
    parser.add_argument("--out", help="Path to program .out")
    parser.add_argument("--timeout-ms", type=int, default=20000, help="DSS script timeout in milliseconds")
    parser.add_argument(
        "--process-timeout-ms",
        type=int,
        help="Outer Python process timeout. Defaults to --timeout-ms plus 20000.",
    )
    parser.add_argument("--keep-js", action="store_true", help="Keep generated temporary DSS JavaScript")

    subparsers = parser.add_subparsers(dest="command", required=True)

    probe = subparsers.add_parser("probe", help="Connect, list reset types, read registers, then halt")
    probe.add_argument("--leave-running", action="store_true", help="Continue target before disconnecting")

    load = subparsers.add_parser("load", help="Load/program the .out through the debug session")
    load.add_argument("--reset", default=None, help='Optional reset type, for example "System Reset"')
    load.add_argument("--leave-running", action="store_true", help="Run target before disconnecting")

    run_symbol = subparsers.add_parser("run-to-symbol", help="Optionally load, reset, then run to a symbol")
    run_symbol.add_argument("--symbol", default="main", help="Symbol name")
    run_symbol.add_argument("--load", action="store_true", help="Load/program .out before running")
    run_symbol.add_argument("--symbols", action="store_true", help="Load symbols from .out without programming flash")
    run_symbol.add_argument("--reset", default="System Reset", help='Reset type, default "System Reset"')
    run_symbol.add_argument("--leave-running", action="store_true", help="Continue target before disconnecting")

    break_line = subparsers.add_parser("break-line", help="Optionally load, reset, then run to source line")
    break_line.add_argument("--source", required=True, help="Source filename or full source path")
    break_line.add_argument("--line", required=True, type=int, help="1-based source line")
    break_line.add_argument("--load", action="store_true", help="Load/program .out before running")
    break_line.add_argument("--symbols", action="store_true", help="Load symbols from .out without programming flash")
    break_line.add_argument("--reset", default="System Reset", help='Reset type, default "System Reset"')
    break_line.add_argument("--leave-running", action="store_true", help="Continue target before disconnecting")

    load_symbols = subparsers.add_parser("load-symbols", help="Load debug symbols from .out without programming flash")
    load_symbols.add_argument("--symbol", action="append", default=[], help="Symbol to resolve. Repeatable.")
    load_symbols.add_argument("--lookup-address", help="Address to look up, for example 0x1bc0")
    load_symbols.add_argument("--lookup-length", type=int_auto, help="Optional lookup range length")
    load_symbols.add_argument("--leave-running", action="store_true", help="Continue target before disconnecting")

    break_address = subparsers.add_parser("break-address", help="Load symbols, set an address breakpoint, then run")
    break_address.add_argument("--address", required=True, help="Breakpoint address, for example 0x1bc0")
    break_address.add_argument("--symbols", action="store_true", help="Load symbols from .out before setting breakpoint")
    break_address.add_argument("--reset", default="System Reset", help='Reset type, default "System Reset"')
    break_address.add_argument("--leave-running", action="store_true", help="Continue target before disconnecting")

    subparsers.add_parser("halt", help="Connect, halt, read registers, disconnect")
    subparsers.add_parser("run", help="Connect, start/continue running, disconnect")

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_arg_parser()
    args = parser.parse_args(argv)

    if args.command in {"run-to-symbol", "break-line"} and args.load and args.symbols:
        parser.error("--load and --symbols are mutually exclusive")

    project_dir = Path(args.project_dir).resolve()
    if not project_dir.exists():
        raise SystemExit(f"error: project directory does not exist: {project_dir}")

    run_bat = find_run_bat(args.ccs_run)
    ccxml = find_ccxml(project_dir, args.ccxml)

    program_required = args.command in {"load", "load-symbols"} or (
        args.command in {"run-to-symbol", "break-line"} and (getattr(args, "load", False) or getattr(args, "symbols", False))
    ) or (
        args.command in {"break-address"} and getattr(args, "symbols", False)
    )
    program = find_program(project_dir, args.out, required=program_required)

    print(
        json.dumps({"event": "wrapper", "backend": "ccs-dss", "run_bat": str(run_bat), "project": str(project_dir)}),
        flush=True,
    )

    if args.command == "probe":
        js_text = make_probe_js(args.timeout_ms, ccxml, args.leave_running)
    elif args.command == "load":
        js_text = make_load_js(args.timeout_ms, ccxml, program, args.reset, args.leave_running)
    elif args.command == "run-to-symbol":
        js_text = make_run_to_symbol_js(
            args.timeout_ms,
            ccxml,
            program if (args.load or args.symbols) else None,
            args.symbols,
            args.symbol,
            args.reset,
            args.leave_running,
        )
    elif args.command == "break-line":
        js_text = make_break_line_js(
            args.timeout_ms,
            ccxml,
            program if (args.load or args.symbols) else None,
            args.symbols,
            args.source,
            args.line,
            args.reset,
            args.leave_running,
        )
    elif args.command == "load-symbols":
        js_text = make_load_symbols_js(
            args.timeout_ms,
            ccxml,
            program,
            args.symbol,
            args.lookup_address,
            args.lookup_length,
            args.leave_running,
        )
    elif args.command == "break-address":
        js_text = make_break_address_js(
            args.timeout_ms,
            ccxml,
            program if args.symbols else None,
            args.address,
            args.reset,
            args.leave_running,
        )
    elif args.command == "halt":
        js_text = make_halt_js(args.timeout_ms, ccxml)
    elif args.command == "run":
        js_text = make_run_js(args.timeout_ms, ccxml)
    else:
        parser.error(f"unsupported command: {args.command}")

    process_timeout_ms = args.process_timeout_ms if args.process_timeout_ms is not None else args.timeout_ms + 20000
    return run_js(run_bat, js_text, args.keep_js, process_timeout_ms)


if __name__ == "__main__":
    raise SystemExit(main())
