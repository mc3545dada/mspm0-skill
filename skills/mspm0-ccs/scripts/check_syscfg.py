#!/usr/bin/env python3
"""Static checker for TI MSPM0 SysConfig projects and common toolchain layouts."""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Iterable

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from detect_probe import detect_probes
from run_sysconfig import inspect_ccs_project


GENERATED_NAMES = {"ti_msp_dl_config.c", "ti_msp_dl_config.h"}
CCS_BUILD_DIRS = {"Debug", "Release"}
KEIL_BUILD_DIRS = {"Objects", "Listings"}
CMAKE_BUILD_PREFIXES = ("cmake-build",)
COMMON_BUILD_DIRS = {"build", "out"}
BUILD_DIRS = CCS_BUILD_DIRS | KEIL_BUILD_DIRS | COMMON_BUILD_DIRS
SKIP_DIRS = {".git", ".svn", ".hg", ".agents", ".claude", ".codex", "__pycache__"}
FRAMEWORK_DIR_NAMES = {
    "app",
    "apps",
    "application",
    "bsp",
    "board",
    "components",
    "core",
    "drivers",
    "hal",
    "middleware",
    "platform",
    "tasks",
    "user",
}
OPENOCD_CONFIG_NAMES = {"daplink.cfg", "stlink.cfg", "xds110.cfg"}
OPENOCD_CONTENT_PATTERNS = (
    r"\bsource\s+\[find\s+",
    r"\btransport\s+select\s+",
    r"\badapter\s+(?:speed|driver|serial)\b",
    r"\binterface\s+",
    r"\bsource\s+.*(?:interface|target|board)/",
    r"\btarget\s+create\s+",
    r"\bflash\s+bank\s+",
    r"\breset_config\b",
    r"\bprogram\s+.+(?:verify|reset|exit)",
)


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
    return sorted(p for p in iter_files(root) if p.suffix == ".syscfg" and not is_build_path(p, root))


def find_generated_files(root: Path) -> list[Path]:
    return sorted(p for p in iter_files(root) if p.name in GENERATED_NAMES)


def find_output_files(root: Path) -> list[Path]:
    output_suffixes = {".out", ".axf", ".elf", ".hex", ".bin"}
    priority = {".out": 0, ".axf": 1, ".elf": 2, ".hex": 3, ".bin": 4}
    outputs = [p for p in iter_files(root) if p.suffix.lower() in output_suffixes]
    return sorted(outputs, key=lambda p: (priority.get(p.suffix.lower(), 99), rel(p, root).lower()))


def find_target_configs(root: Path) -> list[Path]:
    target_dir = root / "targetConfigs"
    if not target_dir.exists():
        return []
    return sorted(target_dir.glob("*.ccxml"))


def find_keil_projects(root: Path) -> list[Path]:
    return sorted(p for p in iter_files(root) if p.suffix.lower() == ".uvprojx" and not is_build_path(p, root))


def find_cmake_files(root: Path) -> list[Path]:
    root_cmake = root / "CMakeLists.txt"
    return [root_cmake] if root_cmake.exists() else []


def find_openocd_configs(root: Path) -> list[Path]:
    configs = [
        p
        for p in iter_files(root)
        if p.suffix.lower() == ".cfg" and not is_build_path(p, root) and is_openocd_config(p)
    ]
    return sorted(configs, key=lambda p: (p.name.lower() not in OPENOCD_CONFIG_NAMES, rel(p, root).lower()))


def find_source_files(root: Path) -> list[Path]:
    suffixes = {".c", ".h", ".cpp", ".cc", ".hpp"}
    files: list[Path] = []
    for path in iter_files(root):
        if path.suffix not in suffixes:
            continue
        if is_build_path(path, root):
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


def is_build_path(path: Path, root: Path) -> bool:
    parts = path.relative_to(root).parts
    return bool(set(parts) & BUILD_DIRS) or any(part.startswith(CMAKE_BUILD_PREFIXES) for part in parts)


def find_build_dirs(root: Path) -> list[Path]:
    build_dirs: list[Path] = []
    for child in root.iterdir():
        if not child.is_dir():
            continue
        if child.name in BUILD_DIRS or child.name.startswith(CMAKE_BUILD_PREFIXES):
            build_dirs.append(child)
    return sorted(build_dirs)


def is_openocd_config(path: Path) -> bool:
    name = path.name.lower()
    text = read_text(path)
    if name in OPENOCD_CONFIG_NAMES and re.search(r"\b(?:source|transport|adapter|interface|target|reset_config|program)\b", text):
        return True
    return any(re.search(pattern, text, flags=re.IGNORECASE) for pattern in OPENOCD_CONTENT_PATTERNS)


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
    sysconfig_script = Path(__file__).resolve().with_name("run_sysconfig.py")
    syscfg_files = find_syscfg_files(root)
    if len(syscfg_files) == 1:
        hints["sysconfig_validate"] = f'python "{sysconfig_script}" "{root}"'
    elif len(syscfg_files) > 1:
        hints["sysconfig_selection"] = (
            "Multiple .syscfg files found. Run run_sysconfig.py with --script <project-relative.syscfg>."
        )
    makefile = root / "Debug" / "subdir_rules.mk"
    if makefile.exists():
        text = read_text(makefile)
        sysconfig = re.search(r'"[^"]*sysconfig_cli\.bat"[^\r\n]+', text)
        if sysconfig:
            hints["sysconfig_cli"] = sysconfig.group(0).strip()
        hints["gmake"] = f'gmake -C "{root / "Debug"}" clean all'

    ccxmls = find_target_configs(root)
    outputs = find_output_files(root)
    dslite_flash_outputs = [p for p in outputs if p.suffix.lower() == ".out"] or outputs
    openocd_flash_outputs = [p for p in outputs if p.suffix.lower() in {".elf", ".hex", ".bin"}]
    if len(ccxmls) == 1:
        hints["list_debug_cores"] = f'dslite -c "{ccxmls[0]}" -N'
        dss_script = Path(__file__).resolve().with_name("ccs_dss_debug.py")
        hints["ccs_dss_probe"] = f'python "{dss_script}" "{root}" probe --leave-running'
    elif len(ccxmls) > 1:
        hints["ccs_target_config_selection"] = (
            "Multiple CCS targetConfigs/*.ccxml files found. Ask the user which probe/config to use before running DSLite or CCS-DSS commands."
        )
    if len(ccxmls) == 1 and len(dslite_flash_outputs) == 1:
        hints["flash"] = f'dslite -c "{ccxmls[0]}" -e -r 2 -u "{dslite_flash_outputs[0]}"'
        hints["ccs_dss_run_to_main"] = (
            f'python "{dss_script}" "{root}" run-to-symbol --symbol main --load --reset "System Reset"'
        )
    elif len(ccxmls) == 1 and len(dslite_flash_outputs) > 1:
        hints["flash"] = "Multiple program outputs found. Choose the intended output explicitly before flashing with DSLite."

    keil_projects = find_keil_projects(root)
    if keil_projects:
        hints["keil_build"] = f'Open "{keil_projects[0]}" in Keil/uVision and build the active target.'

    cmake_info = detect_cmake_info(root)
    if cmake_info["has_cmake"]:
        build_dir = cmake_info["build_dir"]
        target = cmake_info.get("target") or "all"
        if build_dir:
            hints["cmake_build"] = f'cmake --build "{build_dir}" --target {target}'
        else:
            hints["cmake_configure"] = f'cmake -S "{root}" -B "{root / "build"}"'

        flash_target = cmake_info.get("flash_target")
        if build_dir and flash_target:
            hints["openocd_flash"] = f'cmake --build "{build_dir}" --target {flash_target}'
        elif cmake_info["openocd_configs"] and len(openocd_flash_outputs) == 1:
            hints["openocd_flash"] = f'openocd -f "{cmake_info["openocd_configs"][0]}" -c "program \\"{openocd_flash_outputs[0]}\\" verify reset exit"'
        elif cmake_info["openocd_configs"] and len(openocd_flash_outputs) > 1:
            hints["openocd_flash"] = "Multiple OpenOCD-compatible outputs found. Choose the intended output explicitly before flashing."
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


def top_source_dirs(sources: list[Path], root: Path) -> list[str]:
    dirs: set[str] = set()
    for source in sources:
        parts = source.relative_to(root).parts
        if len(parts) > 1:
            dirs.add(parts[0])
    return sorted(dirs)


def detect_framework_info(root: Path, sources: list[Path]) -> dict[str, object]:
    top_dirs = top_source_dirs(sources, root)
    framework_dirs = sorted(name for name in top_dirs if name.lower() in FRAMEWORK_DIR_NAMES)
    source_dirs = sorted({str(source.parent.relative_to(root)) for source in sources})
    is_framework = len(framework_dirs) >= 2 or len(source_dirs) >= 4 or len(sources) >= 12

    if not sources:
        style = "unknown"
    elif is_framework:
        style = "framework_multi_module"
    elif len(sources) <= 3:
        style = "simple_single_app"
    else:
        style = "simple_multi_file"

    return {
        "style": style,
        "top_source_dirs": top_dirs,
        "framework_dirs": framework_dirs,
        "source_count": len(sources),
    }


def detect_rtos_info(root: Path, sources: list[Path]) -> dict[str, object]:
    freertos_files = [p for p in iter_files(root) if p.name in {"FreeRTOSConfig.h", "FreeRTOS.h", "task.h"} and not is_build_path(p, root)]
    freertos_sources: list[str] = []
    for source in sources:
        if source.suffix.lower() not in {".c", ".h", ".cc", ".cpp", ".hpp"}:
            continue
        text = read_text(source)
        if "FreeRTOS.h" in text or "task.h" in text or "xTaskCreate" in text or "vTaskStartScheduler" in text:
            freertos_sources.append(rel(source, root))
            if len(freertos_sources) >= 5:
                break

    detected = bool(freertos_files or freertos_sources)
    return {
        "detected": detected,
        "kind": "FreeRTOS" if detected else "",
        "files": [rel(p, root) for p in freertos_files[:8]],
        "source_mentions": freertos_sources,
    }


def detect_cmake_info(root: Path) -> dict[str, object]:
    cmake_files = find_cmake_files(root)
    build_dirs = find_build_dirs(root)
    openocd_configs = find_openocd_configs(root)
    root_cmake = root / "CMakeLists.txt"
    text = read_text(root_cmake) if root_cmake.exists() else ""

    target = ""
    project_match = re.search(r"project\(\s*\$\{?CMAKE_PROJECT_NAME\}?", text)
    if project_match:
        name_match = re.search(r"set\(\s*CMAKE_PROJECT_NAME\s+([A-Za-z0-9_.-]+)\s*\)", text)
        if name_match:
            target = name_match.group(1)
    if not target:
        add_exe = re.search(r"add_executable\(\s*([A-Za-z0-9_.-]+)", text)
        if add_exe:
            target = add_exe.group(1)

    flash_target = ""
    flash_match = re.search(r"add_custom_target\(\s*([A-Za-z0-9_.-]*flash[A-Za-z0-9_.-]*)", text, flags=re.IGNORECASE)
    if flash_match:
        flash_target = flash_match.group(1)

    uses_gcc = "arm-none-eabi" in text or "CMAKE_C_COMPILER" in text
    uses_openocd = "openocd" in text.lower() or bool(openocd_configs)

    return {
        "has_cmake": bool(cmake_files),
        "cmake_files": [rel(p, root) for p in cmake_files],
        "build_dirs": [rel(p, root) for p in build_dirs],
        "build_dir": build_dirs[0] if build_dirs else None,
        "target": target,
        "flash_target": flash_target,
        "uses_gcc": uses_gcc,
        "uses_openocd": uses_openocd,
        "openocd_configs": [rel(p, root) for p in openocd_configs],
    }


def check_project(root: Path) -> tuple[list[Message], dict[str, object]]:
    messages: list[Message] = []
    details: dict[str, object] = {}

    if not root.is_dir():
        messages.append(Message("error", "Project directory does not exist or is not a directory.", str(root)))
        return messages, details

    syscfg_files = find_syscfg_files(root)
    details["syscfg_files"] = [rel(p, root) for p in syscfg_files]
    keil_projects = find_keil_projects(root)
    source_files = find_source_files(root)
    framework_info = detect_framework_info(root, source_files)
    rtos_info = detect_rtos_info(root, source_files)
    cmake_info = detect_cmake_info(root)

    details["project_style"] = framework_info
    details["rtos"] = rtos_info
    details["cmake"] = {
        key: (str(value) if isinstance(value, Path) else value)
        for key, value in cmake_info.items()
    }
    try:
        ccs_project = inspect_ccs_project(root)
    except RuntimeError as exc:
        ccs_project = {"products": {}, "compiler": "", "error": str(exc)}
        messages.append(Message("warning", f"无法解析 CCS .cproject 产品声明：{exc}"))
    details["ccs_project"] = ccs_project
    ccs_products = ccs_project.get("products", {})
    if isinstance(ccs_products, dict) and ccs_products:
        product_text = ", ".join(f"{name}:{version}" for name, version in sorted(ccs_products.items()))
        compiler = str(ccs_project.get("compiler", "")) or "未识别"
        messages.append(Message("info", f"CCS 工程声明产品：{product_text}；SysConfig compiler={compiler}。"))
    ccs_product_conflicts = ccs_project.get("product_conflicts", {})
    if isinstance(ccs_product_conflicts, dict) and ccs_product_conflicts:
        conflict_text = ", ".join(
            f"{name}:{'/'.join(versions)}"
            for name, versions in sorted(ccs_product_conflicts.items())
        )
        messages.append(
            Message(
                "warning",
                f"CCS 各构建配置的产品版本不一致：{conflict_text}；"
                "运行 SysConfig CLI 前请显式选择工具或 SDK。",
            )
        )
    ccs_compiler_conflicts = ccs_project.get("compiler_conflicts", [])
    if isinstance(ccs_compiler_conflicts, list) and ccs_compiler_conflicts:
        messages.append(
            Message(
                "warning",
                "CCS 各构建配置的 SysConfig compiler 不一致："
                f"{'/'.join(str(item) for item in ccs_compiler_conflicts)}；"
                "运行 SysConfig CLI 前请使用 --compiler 显式选择。",
            )
        )

    if framework_info["style"] == "framework_multi_module":
        dirs = ", ".join(framework_info["framework_dirs"][:8]) or ", ".join(framework_info["top_source_dirs"][:8])
        messages.append(Message("info", f"项目结构：framework_multi_module，发现多层源码目录 {dirs}；修改前应先确认 app/BSP/driver/core 等模块边界。"))
    elif framework_info["style"] in {"simple_single_app", "simple_multi_file"}:
        messages.append(Message("info", f"项目结构：{framework_info['style']}。"))

    if rtos_info["detected"]:
        messages.append(Message("info", "检测到 FreeRTOS 线索；新增外设逻辑时应确认任务、队列、中断和阻塞调用边界。"))

    if cmake_info["has_cmake"]:
        messages.append(Message("info", "发现 CMake 工程；应通过 CMake/GCC 或项目指定工具链构建，而不是假定 CCS/Keil。"))
        if cmake_info["uses_gcc"]:
            messages.append(Message("info", "CMake 配置包含 arm-none-eabi/GCC 工具链线索。"))
        if cmake_info["uses_openocd"]:
            configs = ", ".join(cmake_info["openocd_configs"][:5])
            suffix = f"：{configs}" if configs else ""
            messages.append(Message("info", f"发现 OpenOCD 配置或烧录目标{suffix}。MSPM0 通常需要 TI 扩展分支 OpenOCD。"))
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
        ccs_generated = [p for p in generated if has_part(p, root, CCS_BUILD_DIRS)]
        keil_style_generated = [p for p in generated if not has_part(p, root, CCS_BUILD_DIRS)]
        if ccs_generated:
            messages.append(Message("info", "发现 CCS Debug/Release 下的 SysConfig 生成文件；只能读取确认宏名，不要手动修改。"))
        if keil_style_generated:
            messages.append(Message("info", "发现工程源目录或 Keil 风格布局中的 SysConfig 生成文件；只能读取确认宏名，不要手动修改。"))
    else:
        messages.append(Message("warning", "未发现 ti_msp_dl_config.c/.h，工程可能尚未生成或尚未编译。"))

    headers = [p for p in generated if p.name == "ti_msp_dl_config.h"]
    header_init_names = parse_header_init_names(headers)
    details["header_init_names"] = sorted(header_init_names)

    source_calls = parse_source_init_calls(source_files)
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
    has_ccs_build = makefile.exists() and subdir_rules.exists()
    if has_ccs_build:
        messages.append(Message("ok", "Debug 构建文件已存在，可以尝试使用 gmake -C Debug clean all。", "Debug"))
        if has_duplicate_linker_cmd_inputs(root):
            messages.append(Message("warning", "Debug/makefile 同时引用 ../device_linker.cmd 和 ./device_linker.cmd；这可能导致 gmake clean all 失败或重复链接 linker cmd。优先让 CCS 重新生成构建文件，临时 CLI 验证时避免重复输入。", "Debug/makefile"))
    if keil_projects:
        messages.append(Message("info", f"发现 Keil/uVision 工程：{rel(keil_projects[0], root)}。请检查 .uvprojx、Objects/ 和 Listings/。", rel(keil_projects[0], root)))
    if not has_ccs_build and not keil_projects and not cmake_info["has_cmake"]:
        messages.append(Message("warning", "Debug 构建文件不完整；新建工程通常需要先在 CCS/CCS Theia 编译一次，或使用 CCS 命令行构建生成 makefile。", "Debug"))
    elif cmake_info["has_cmake"] and not has_ccs_build and not keil_projects:
        messages.append(Message("info", "未发现 CCS Debug 构建文件；当前更像 CMake 工程，请使用 CMake 构建目录和目标。"))

    outputs = find_output_files(root)
    details["output_files"] = [rel(p, root) for p in outputs]
    if outputs:
        messages.append(Message("ok", f"发现可烧录输出文件：{rel(outputs[0], root)}。", rel(outputs[0], root)))
    else:
        messages.append(Message("warning", "未发现可烧录输出文件（.out/.axf/.elf/.hex/.bin）；烧录前需要先成功构建工程。"))

    ccxmls = find_target_configs(root)
    keil_projects = find_keil_projects(root)
    details["target_configs"] = [{"path": rel(p, root), "probe": describe_target_config(p)} for p in ccxmls]
    details["keil_projects"] = [rel(p, root) for p in keil_projects]
    if ccxmls:
        for ccxml in ccxmls:
            probe = describe_target_config(ccxml)
            messages.append(Message("info", f"目标配置使用调试器：{probe}。请确认它和实际连接的烧录器一致。", rel(ccxml, root)))
    if len(ccxmls) > 1:
        messages.append(Message("warning", "Multiple CCS targetConfigs/*.ccxml files were found. Ask the user which probe/config to use before running DSLite or CCS-DSS commands."))
    if keil_projects and not ccxmls:
        messages.append(Message("info", "未发现 targetConfigs/*.ccxml；当前是 Keil 工程，通常通过 `.uvprojx` 和 Keil 调试器配置来验证。"))
    elif keil_projects:
        messages.append(Message("info", "同时发现 Keil/uVision 工程；如果当前使用 Keil 工作流，请确认 `.uvprojx` 和 Keil 调试器配置。"))
    if not ccxmls and not keil_projects and not cmake_info["uses_openocd"]:
        messages.append(Message("warning", "未发现 targetConfigs/*.ccxml；DSLite 烧录需要目标配置文件。"))
    elif cmake_info["uses_openocd"] and not ccxmls:
        messages.append(Message("info", "未发现 targetConfigs/*.ccxml；当前更像 OpenOCD 烧录路径，不需要 CCS targetConfigs。"))

    details["validation_hints"] = find_validation_hints(root)
    return messages, details


def add_probe_check(root: Path, messages: list[Message], details: dict[str, object]) -> None:
    hints = details.setdefault("validation_hints", {})
    assert isinstance(hints, dict)
    detector = Path(__file__).resolve().with_name("detect_probe.py")
    hints["detect_probe"] = f'python "{detector}"'
    try:
        probes = detect_probes()
    except Exception as exc:  # Keep static checks usable when OS probe enumeration is unavailable.
        details["connected_probes"] = {"error": str(exc), "probes": []}
        messages.append(Message("warning", f"Connected probe detection failed: {exc}"))
        return

    serialized = [asdict(probe) for probe in probes]
    details["connected_probes"] = {"probes": serialized}
    if not probes:
        messages.append(
            Message(
                "warning",
                "No supported debug probe was identified by the primary scan. This is inconclusive, not proof that no probe is connected; inspect OS USB/PnP and serial devices or use the backend's own probe command before flashing.",
            )
        )
        return
    if len(probes) > 1:
        kinds = ", ".join(probe.kind for probe in probes)
        messages.append(Message("warning", f"Multiple connected debug probes were detected: {kinds}. Ask the user which probe to use before flashing."))
    for probe in probes:
        suffix = f", USB {probe.usb_id}" if probe.usb_id else ""
        config = f", config {probe.recommended_config}" if probe.recommended_config else ""
        messages.append(
            Message(
                "info",
                f"Connected probe: {probe.kind} ({probe.display_name}{suffix}). Recommended backend: {probe.recommended_backend}{config}.",
            )
        )

    if len(probes) != 1:
        return
    connected = probes[0]
    ccxmls = find_target_configs(root)
    configured = {describe_target_config(path) for path in ccxmls}
    configured_probe_kinds = {
        kind
        for name, kind in (
            ("SEGGER J-Link", "jlink"),
            ("TI XDS110", "xds110"),
        )
        if name in configured
    }
    mismatch = bool(configured_probe_kinds) and connected.kind not in configured_probe_kinds
    if mismatch:
        expected = ", ".join(sorted(configured))
        for key in ("list_debug_cores", "ccs_dss_probe", "flash", "ccs_dss_run_to_main"):
            hints.pop(key, None)
        hints["probe_mismatch"] = "Stop before flashing. Ask the user to confirm the intended probe/backend."
        messages.append(
            Message(
                "warning",
                f"Connected probe {connected.kind} does not match CCS target config ({expected}). Do not flash through that CCS/DSLite config until the user confirms the backend.",
            )
        )
    if connected.kind == "cmsis-dap":
        openocd_script = Path(__file__).resolve().with_name("openocd_debug.py")
        hints["openocd_probe"] = f'python "{openocd_script}" "{root}" probe'
        outputs = find_output_files(root)
        if len(outputs) == 1:
            hints["openocd_flash"] = f'python "{openocd_script}" "{root}" flash --program "{outputs[0]}"'
        elif len(outputs) > 1:
            hints["openocd_flash"] = "Multiple program outputs found. Choose one explicitly with openocd_debug.py flash --program <path>."
            messages.append(Message("warning", "Multiple program outputs were found. OpenOCD flashing requires an explicit --program path."))
        messages.append(
            Message(
                "info",
                "CMSIS-DAP / DAPLink is connected. Prefer the OpenOCD path with interface/cmsis-dap.cfg unless the project intentionally declares another verified backend.",
            )
        )


def print_text(root: Path, messages: list[Message], details: dict[str, object]) -> None:
    print(f"MSPM0 SysConfig static check: {root}")
    for msg in messages:
        path = f" [{msg.path}]" if msg.path else ""
        print(f"{msg.level.upper():7} {msg.text}{path}")

    hints = details.get("validation_hints", {})
    if isinstance(hints, dict) and hints:
        print()
        print("Suggested CLI validation chain:")
        for key in (
            "detect_probe",
            "sysconfig_validate",
            "sysconfig_selection",
            "sysconfig_cli",
            "gmake",
            "cmake_configure",
            "cmake_build",
            "keil_build",
            "ccs_target_config_selection",
            "list_debug_cores",
            "ccs_dss_probe",
            "flash",
            "ccs_dss_run_to_main",
            "openocd_probe",
            "openocd_flash",
            "probe_mismatch",
        ):
            if key in hints:
                print(f"- {key}: {hints[key]}")


def main() -> int:
    parser = argparse.ArgumentParser(description="Check an MSPM0 SysConfig project.")
    parser.add_argument("project", nargs="?", default=".", help="Path to a project directory.")
    parser.add_argument("--json", action="store_true", help="Print machine-readable JSON.")
    parser.add_argument("--probe", action="store_true", help="Also detect connected debug probes and compare them with project hints.")
    args = parser.parse_args()

    root = Path(args.project).resolve()
    messages, details = check_project(root)
    if args.probe and root.is_dir():
        add_probe_check(root, messages, details)
    has_error = any(msg.level == "error" for msg in messages)

    if args.json:
        print(json.dumps({"project": str(root), "messages": [asdict(m) for m in messages], "details": details}, ensure_ascii=False, indent=2))
    else:
        print_text(root, messages, details)

    return 1 if has_error else 0


if __name__ == "__main__":
    raise SystemExit(main())
