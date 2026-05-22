#!/usr/bin/env python3
"""Static checker for TI MSPM0 SysConfig projects and common CCS / Keil layouts."""

from __future__ import annotations

import argparse
import json
import os
import re
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Iterable


GENERATED_NAMES = {"ti_msp_dl_config.c", "ti_msp_dl_config.h"}
BUILD_DIRS = {"Debug", "Release"}
SKIP_DIRS = {".git", ".svn", ".hg", ".agents", ".claude", ".codex", "__pycache__"}


@dataclass
class Message:
    level: str
    text: str
    path: str | None = None


def rel(path: Path, root: Path) -> str:
    try:
        return str(path.relative_to(root))
    except ValueError:
        return str(path)


def read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="replace")


def find_syscfg_files(root: Path) -> list[Path]:
    return sorted(p for p in iter_files(root) if p.suffix == ".syscfg" and not has_part(p, root, BUILD_DIRS))


def find_generated_files(root: Path) -> list[Path]:
    return sorted(p for p in iter_files(root) if p.name in GENERATED_NAMES and not has_part(p, root, BUILD_DIRS))


def find_output_files(root: Path) -> list[Path]:
    output_suffixes = {".out", ".axf", ".hex"}
    return sorted(p for p in iter_files(root) if p.suffix in output_suffixes and not has_part(p, root, BUILD_DIRS))


def find_target_configs(root: Path) -> list[Path]:
    target_dir = root / "targetConfigs"
    if not target_dir.exists():
        return []
    return sorted(target_dir.glob("*.ccxml"))


def find_keil_projects(root: Path) -> list[Path]:
    keil_dir = root / "keil"
    if not keil_dir.exists():
        return []
    return sorted(keil_dir.glob("*.uvprojx"))


def find_source_files(root: Path) -> list[Path]:
    suffixes = {".c", ".h", ".cpp", ".cc", ".hpp"}
    files: list[Path] = []
    for path in iter_files(root):
        if path.suffix not in suffixes:
            continue
        if has_part(path, root, BUILD_DIRS):
            continue
        if path.name in GENERATED_NAMES:
            continue
        files.append(path)
    return sorted(files)


def iter_files(root: Path) -> Iterable[Path]:
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [name for name in dirnames if name not in SKIP_DIRS]
        for filename in filenames:
            yield Path(dirpath) / filename


def has_part(path: Path, root: Path, parts: set[str]) -> bool:
    return bool(set(path.relative_to(root).parts) & parts)


def parse_metadata(text: str) -> dict[str, str | bool]:
    fields: dict[str, str | bool] = {}
    fields["has_cliArgs"] = "@cliArgs" in text or "@v2CliArgs" in text
    fields["has_versions"] = "@versions" in text

    for key in ("device", "package", "product", "part"):
        match = re.search(rf"--{key}\s+\"([^\"]+)\"", text)
        if match:
            fields[key] = match.group(1)

    version_match = re.search(r"@versions\s+(\{[^\n]+\})", text)
    if version_match:
        fields["versions"] = version_match.group(1).strip()

    return fields


def metadata_comment_syntax_errors(text: str) -> list[int]:
    errors: list[int] = []
    in_block = False
    for lineno, line in enumerate(text.splitlines(), start=1):
        stripped = line.strip()
        before = in_block
        if "/*" in stripped:
            in_block = True
        if stripped.startswith("* @") and not before:
            errors.append(lineno)
        if "*/" in stripped:
            in_block = False
    return errors


def parse_assigned_pins(text: str) -> list[dict[str, str]]:
    pins: list[dict[str, str]] = []
    for match in re.finditer(
        r"(?P<expr>[A-Za-z0-9_.$\[\]]+associatedPins\[\d+\])\.assignedPin\s*=\s*\"(?P<pin>[^\"]+)\"",
        text,
    ):
        expr = match.group("expr")
        pin = match.group("pin")
        suggestion = ""
        pattern = re.escape(expr) + r"\.pin\.\$suggestSolution\s*=\s*\"([^\"]+)\""
        suggestion_match = re.search(pattern, text)
        if suggestion_match:
            suggestion = suggestion_match.group(1)
        pins.append({"expr": expr, "assignedPin": pin, "suggestSolution": suggestion})
    return pins


def parse_peripheral_pin_assigns(text: str) -> list[dict[str, str]]:
    pins: list[dict[str, str]] = []
    for match in re.finditer(
        r"(?P<expr>[A-Za-z0-9_.$\[\]]+(?:Pin|pin))\.\$assign\s*=\s*\"(?P<pin>P[A-Z]\d+)\"",
        text,
    ):
        pins.append({"expr": match.group("expr"), "pin": match.group("pin")})
    return pins


def parse_hfxt_status(text: str) -> dict[str, bool]:
    clock_tree_match = re.search(r"(?:const|let|var)\s+([A-Za-z_][A-Za-z0-9_]*)\s*=\s*system\.clockTree\[\s*[\"']HFXT[\"']\s*\]", text)
    clock_tree_enabled = False
    if clock_tree_match:
        variable = re.escape(clock_tree_match.group(1))
        clock_tree_enabled = bool(re.search(rf"\b{variable}\.enable\s*=\s*true", text))
    sysctl_uses_hfxt = bool(re.search(r"SYSCTL\.HFCLKSource\s*=\s*[\"']HFXT[\"']", text))
    enabled = clock_tree_enabled or sysctl_uses_hfxt
    has_in_pin_lock = bool(re.search(r"(hfxInPin|GPIO_HFXIN|HFXIN).*\$(assign|suggestSolution)", text))
    has_out_pin_lock = bool(re.search(r"(hfxOutPin|GPIO_HFXOUT|HFXOUT).*\$(assign|suggestSolution)", text))
    return {
        "enabled": enabled,
        "has_hfxin_lock": has_in_pin_lock,
        "has_hfxout_lock": has_out_pin_lock,
    }


def parse_header_init_names(headers: Iterable[Path]) -> set[str]:
    names: set[str] = set()
    for header in headers:
        text = read_text(header)
        names.update(re.findall(r"\bvoid\s+(SYSCFG_DL_[A-Za-z]*[Ii]nit)\s*\(", text))
    return names


def parse_source_init_calls(sources: Iterable[Path]) -> dict[str, list[str]]:
    calls: dict[str, list[str]] = {}
    for source in sources:
        text = read_text(source)
        names = sorted(set(re.findall(r"\b(SYSCFG_DL_[A-Za-z]*[Ii]nit)\s*\(", text)))
        if names:
            calls[str(source)] = names
    return calls


def find_validation_hints(root: Path) -> dict[str, str]:
    hints: dict[str, str] = {}
    makefile = root / "Debug" / "subdir_rules.mk"
    if makefile.exists():
        text = read_text(makefile)
        sysconfig = re.search(r'"[^"]*sysconfig_cli\.bat"[^\r\n]+', text)
        if sysconfig:
            hints["sysconfig_cli"] = sysconfig.group(0).strip()
        hints["gmake"] = f'gmake -C "{root / "Debug"}" clean all'

    ccxmls = find_target_configs(root)
    outs = sorted((root / "Debug").glob("*.out"))
    if ccxmls:
        hints["list_debug_cores"] = f'dslite -c "{ccxmls[0]}" -N'
    if ccxmls and outs:
        hints["flash"] = f'dslite -c "{ccxmls[0]}" -e -r 2 -u "{outs[0]}"'

    keil_projects = find_keil_projects(root)
    if keil_projects:
        hints["keil_build"] = f'Open "{keil_projects[0]}" in Keil/uVision and build the active target.'
    return hints


def has_duplicate_linker_cmd_inputs(root: Path) -> bool:
    makefile = root / "Debug" / "makefile"
    if not makefile.exists():
        return False
    text = read_text(makefile)
    return "../device_linker.cmd" in text and './device_linker.cmd' in text


def describe_target_config(path: Path) -> str:
    text = read_text(path)
    if "segger_j-link_connection.xml" in text or "SEGGER J-Link" in text:
        return "SEGGER J-Link"
    if "TIXDS110_Connection.xml" in text or "XDS110" in text:
        return "TI XDS110"
    return "unknown"


def check_project(root: Path) -> tuple[list[Message], dict[str, object]]:
    messages: list[Message] = []
    details: dict[str, object] = {}

    syscfg_files = find_syscfg_files(root)
    details["syscfg_files"] = [rel(p, root) for p in syscfg_files]
    keil_projects = find_keil_projects(root)
    if not syscfg_files:
        messages.append(Message("error", "没有找到 .syscfg 文件。"))
    elif len(syscfg_files) > 1:
        messages.append(Message("warning", "找到多个 .syscfg 文件，修改前需要确认当前工程使用哪一个。"))
    else:
        messages.append(Message("ok", f"找到 .syscfg：{rel(syscfg_files[0], root)}", rel(syscfg_files[0], root)))

    for syscfg in syscfg_files:
        text = read_text(syscfg)
        metadata = parse_metadata(text)
        details[f"metadata:{rel(syscfg, root)}"] = metadata
        syntax_errors = metadata_comment_syntax_errors(text)
        if syntax_errors:
            messages.append(Message("error", f"疑似无效的 SysConfig 元数据注释行：{', '.join(map(str, syntax_errors))}。", rel(syscfg, root)))
        if metadata.get("has_cliArgs"):
            messages.append(Message("ok", ".syscfg 保留了 @cliArgs / @v2CliArgs 元数据。", rel(syscfg, root)))
        else:
            messages.append(Message("warning", ".syscfg 未发现 @cliArgs / @v2CliArgs，SysConfig 设备/封装信息可能不完整。", rel(syscfg, root)))
        if metadata.get("has_versions"):
            messages.append(Message("ok", ".syscfg 保留了 @versions 元数据。", rel(syscfg, root)))
        else:
            messages.append(Message("warning", ".syscfg 未发现 @versions，可能是未编译空工程或旧模板，需要用 CCS/SysConfig 确认工具版本。", rel(syscfg, root)))

        pins = parse_assigned_pins(text)
        details[f"assigned_pins:{rel(syscfg, root)}"] = pins
        peripheral_pin_assigns = parse_peripheral_pin_assigns(text)
        details[f"peripheral_pin_assigns:{rel(syscfg, root)}"] = peripheral_pin_assigns
        if pins:
            for pin in pins:
                suffix = f"，建议解为 {pin['suggestSolution']}" if pin["suggestSolution"] else ""
                messages.append(Message("ok", f"发现 assignedPin={pin['assignedPin']}{suffix}。", rel(syscfg, root)))
        elif peripheral_pin_assigns:
            formatted = ", ".join(f"{pin['expr']}={pin['pin']}" for pin in peripheral_pin_assigns[:5])
            more = " ..." if len(peripheral_pin_assigns) > 5 else ""
            messages.append(Message("ok", f"发现外设 pin $assign：{formatted}{more}。", rel(syscfg, root)))
        elif "/ti/driverlib/GPIO" in text:
            messages.append(Message("warning", "导入了 GPIO 模块，但没有发现 assignedPin；请确认是否依赖自动求解。", rel(syscfg, root)))
        else:
            messages.append(Message("info", "未发现 assignedPin；如果是空工程，这是正常现象。", rel(syscfg, root)))

        hfxt_status = parse_hfxt_status(text)
        details[f"hfxt:{rel(syscfg, root)}"] = hfxt_status
        if hfxt_status["enabled"]:
            if hfxt_status["has_hfxin_lock"] and hfxt_status["has_hfxout_lock"]:
                messages.append(Message("ok", "HFXT 已启用，并发现 HFXIN/HFXOUT pinmux 锁定线索。", rel(syscfg, root)))
            else:
                messages.append(Message("warning", "HFXT 已启用，但未发现 HFXIN/HFXOUT pinmux 锁定线索；GUI 可能显示 Solution may have changed warning，请确认 PA5/PA6 和生成头文件。", rel(syscfg, root)))

    generated = find_generated_files(root)
    details["generated_files"] = [rel(p, root) for p in generated]
    if generated:
        messages.append(Message("info", "发现 SysConfig 生成文件；只能读取确认宏名，不要手动修改。"))
    else:
        messages.append(Message("warning", "未发现 Debug/Release 下的 ti_msp_dl_config.c/.h，工程可能尚未生成或尚未编译。"))

    headers = [p for p in generated if p.name == "ti_msp_dl_config.h"]
    header_init_names = parse_header_init_names(headers)
    details["header_init_names"] = sorted(header_init_names)

    source_calls = parse_source_init_calls(find_source_files(root))
    details["source_init_calls"] = {rel(Path(k), root): v for k, v in source_calls.items()}
    called_names = {name for names in source_calls.values() for name in names}

    if header_init_names:
        messages.append(Message("ok", f"生成头文件声明初始化函数：{', '.join(sorted(header_init_names))}。"))
        if called_names:
            missing = called_names - header_init_names
            if missing:
                messages.append(Message("error", f"应用代码调用了生成头文件中不存在的初始化函数：{', '.join(sorted(missing))}。"))
            else:
                messages.append(Message("ok", "应用代码调用的 SYSCFG_DL_init 大小写与生成头文件一致。"))
        else:
            messages.append(Message("warning", "应用源码中没有发现 SYSCFG_DL_init/SYSCFG_DL_Init 调用。"))
    else:
        if called_names:
            messages.append(Message("warning", f"源码调用了 {', '.join(sorted(called_names))}，但当前没有生成头文件可确认大小写。"))
        else:
            messages.append(Message("warning", "没有生成头文件，也没有在源码中发现 SysConfig 初始化函数调用。"))

    makefile = root / "Debug" / "makefile"
    subdir_rules = root / "Debug" / "subdir_rules.mk"
    if makefile.exists() and subdir_rules.exists():
        messages.append(Message("ok", "Debug 构建文件已存在，可以尝试使用 gmake -C Debug clean all。", "Debug"))
        if has_duplicate_linker_cmd_inputs(root):
            messages.append(Message("warning", "Debug/makefile 同时引用 ../device_linker.cmd 和 ./device_linker.cmd；这可能导致 gmake clean all 失败或重复链接 linker cmd。优先让 CCS 重新生成构建文件，临时 CLI 验证时避免重复输入。", "Debug/makefile"))
    elif keil_projects:
        messages.append(Message("info", "未发现 CCS Debug 构建文件；当前是 Keil 工程，请检查 .uvprojx、Objects/ 和 Listings/。"))
    else:
        messages.append(Message("warning", "Debug 构建文件不完整；新建工程通常需要先在 CCS/CCS Theia 编译一次，或使用 CCS 命令行构建生成 makefile。", "Debug"))

    outputs = find_output_files(root)
    details["output_files"] = [rel(p, root) for p in outputs]
    if outputs:
        messages.append(Message("ok", f"发现可烧录输出文件：{rel(outputs[0], root)}。", rel(outputs[0], root)))
    else:
        messages.append(Message("warning", "未发现可烧录输出文件（.out/.axf/.hex）；烧录前需要先成功构建工程。"))

    ccxmls = find_target_configs(root)
    keil_projects = find_keil_projects(root)
    details["target_configs"] = [{"path": rel(p, root), "probe": describe_target_config(p)} for p in ccxmls]
    details["keil_projects"] = [rel(p, root) for p in keil_projects]
    if ccxmls:
        for ccxml in ccxmls:
            probe = describe_target_config(ccxml)
            messages.append(Message("info", f"目标配置使用调试器：{probe}。请确认它和实际连接的烧录器一致。", rel(ccxml, root)))
    elif keil_projects:
        messages.append(Message("info", "未发现 targetConfigs/*.ccxml；当前是 Keil 工程，通常通过 `.uvprojx` 和 Keil 调试器配置来验证。"))
    else:
        messages.append(Message("warning", "未发现 targetConfigs/*.ccxml；DSLite 烧录需要目标配置文件。"))

    details["validation_hints"] = find_validation_hints(root)
    return messages, details


def print_text(root: Path, messages: list[Message], details: dict[str, object]) -> None:
    print(f"MSPM0 SysConfig static check: {root}")
    for msg in messages:
        path = f" [{msg.path}]" if msg.path else ""
        print(f"{msg.level.upper():7} {msg.text}{path}")

    hints = details.get("validation_hints", {})
    if isinstance(hints, dict) and hints:
        print()
        print("Suggested CLI validation chain:")
        for key in ("sysconfig_cli", "gmake", "keil_build", "list_debug_cores", "flash"):
            if key in hints:
                print(f"- {key}: {hints[key]}")


def main() -> int:
    parser = argparse.ArgumentParser(description="Check an MSPM0 SysConfig project.")
    parser.add_argument("project", nargs="?", default=".", help="Path to a project directory.")
    parser.add_argument("--json", action="store_true", help="Print machine-readable JSON.")
    args = parser.parse_args()

    root = Path(args.project).resolve()
    messages, details = check_project(root)
    has_error = any(msg.level == "error" for msg in messages)

    if args.json:
        print(json.dumps({"project": str(root), "messages": [asdict(m) for m in messages], "details": details}, ensure_ascii=False, indent=2))
    else:
        print_text(root, messages, details)

    return 1 if has_error else 0


if __name__ == "__main__":
    raise SystemExit(main())
