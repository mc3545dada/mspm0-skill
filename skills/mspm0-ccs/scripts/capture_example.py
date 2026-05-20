#!/usr/bin/env python3
"""Capture a compact MSPM0 CCS project example for the mspm0-ccs skill."""

from __future__ import annotations

import argparse
import fnmatch
import json
import os
import re
import shutil
from pathlib import Path
from typing import Any, Iterable


BUILD_DIRS = {"Debug", "Release"}
SKIP_DIRS = {".git", ".svn", ".hg", ".metadata", ".settings", "__pycache__", ".agents", ".claude", ".codex"}
GENERATED_NAMES = {
    "ti_msp_dl_config.c",
    "ti_msp_dl_config.h",
    "device.opt",
    "device_linker.cmd",
    "device.cmd.genlibs",
    "Event.dot",
}
DEFAULT_EXCLUDES = [
    "Debug/**",
    "Release/**",
    "**/*.o",
    "**/*.d",
    "**/*.out",
    "**/*.map",
    "**/*_linkInfo.xml",
    "**/ti_msp_dl_config.c",
    "**/ti_msp_dl_config.h",
    "**/device_linker.cmd",
    "**/device.opt",
    "**/device.cmd.genlibs",
]


def read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="replace")


def iter_files(root: Path) -> Iterable[Path]:
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [name for name in dirnames if name not in SKIP_DIRS and name not in BUILD_DIRS]
        for filename in filenames:
            yield Path(dirpath) / filename


def rel_posix(path: Path, root: Path) -> str:
    return path.relative_to(root).as_posix()


def matches_any(value: str, patterns: Iterable[str]) -> bool:
    return any(fnmatch.fnmatch(value, pattern) for pattern in patterns)


def find_syscfg(project: Path, explicit: str | None) -> Path:
    if explicit:
        path = (project / explicit).resolve()
        if not path.exists():
            raise SystemExit(f"SysConfig file not found: {path}")
        return path

    syscfgs = sorted(p for p in iter_files(project) if p.suffix == ".syscfg")
    if len(syscfgs) == 1:
        return syscfgs[0]
    if not syscfgs:
        raise SystemExit("No .syscfg file found. Pass --syscfg explicitly if needed.")
    options = "\n".join(f"  - {rel_posix(path, project)}" for path in syscfgs)
    raise SystemExit(f"Multiple .syscfg files found. Pass --syscfg explicitly:\n{options}")


def select_sources(project: Path, includes: list[str], excludes: list[str], auto: bool) -> list[Path]:
    if not includes and not auto:
        raise SystemExit("Pass one or more --include patterns, or use --auto for a best-effort capture.")

    files = []
    for path in iter_files(project):
        rel = rel_posix(path, project)
        if matches_any(rel, excludes):
            continue
        if path.name in GENERATED_NAMES:
            continue
        if includes and matches_any(rel, includes):
            files.append(path)
            continue
        if auto and is_auto_source(path, rel):
            files.append(path)

    return sorted(set(files))


def is_auto_source(path: Path, rel: str) -> bool:
    if path.suffix.lower() not in {".c", ".h", ".cpp", ".cc", ".hpp"}:
        return False
    top = rel.split("/", 1)[0]
    if "/" not in rel:
        return True
    return top in {"src", "app", "bsp", "board", "drivers", "include", "user", "Core"}


def parse_metadata(syscfg_text: str) -> dict[str, Any]:
    metadata: dict[str, Any] = {}
    for key in ("device", "package", "product", "part"):
        match = re.search(rf"--{key}\s+\"([^\"]+)\"", syscfg_text)
        if match:
            metadata[key] = match.group(1)
    versions = re.search(r"@versions\s+(\{[^\n]+\})", syscfg_text)
    if versions:
        metadata["versions"] = versions.group(1).strip()
    return metadata


def parse_modules(syscfg_text: str) -> list[str]:
    modules = set()
    for match in re.finditer(r'scripting\.addModule\("([^"]+)"', syscfg_text):
        modules.add(match.group(1).rsplit("/", 1)[-1])
    return sorted(modules)


def parse_pins(syscfg_text: str) -> list[str]:
    pins = set(re.findall(r'\$assign\s*=\s*"(P[A-Z]\d+)"', syscfg_text))
    pins.update(re.findall(r'\$suggestSolution\s*=\s*"(P[A-Z]\d+)"', syscfg_text))
    for pin in re.findall(r"assignedPin\s*=\s*\"(\d+)\"", syscfg_text):
        pins.add(f"pin:{pin}")
    return sorted(pins)


def detect_generated_names(project: Path) -> list[str]:
    headers = sorted(project.glob("Debug/**/ti_msp_dl_config.h")) + sorted(project.glob("Release/**/ti_msp_dl_config.h"))
    names: set[str] = set()
    for header in headers:
        text = read_text(header)
        names.update(re.findall(r"^#define\s+([A-Za-z_][A-Za-z0-9_]*)", text, flags=re.MULTILINE))
        names.update(re.findall(r"\bvoid\s+(SYSCFG_DL_[A-Za-z]*[Ii]nit)\s*\(", text))
    return sorted(name for name in names if not name.startswith("__"))[:80]


def source_mentions_freertos(files: list[Path]) -> bool:
    for path in files:
        try:
            text = read_text(path)
        except OSError:
            continue
        if "FreeRTOS" in text or "task.h" in text or "xTaskCreate" in text:
            return True
    return False


def classify_complexity(peripherals: list[str], pins: list[str], sources: list[Path], freertos: bool) -> str:
    if freertos or len(peripherals) >= 8 or len(pins) >= 12 or len(sources) >= 16:
        return "advanced"
    if len(peripherals) >= 5 or len(pins) >= 6 or len(sources) >= 6:
        return "intermediate"
    return "basic"


def bool_arg(value: str) -> bool:
    lowered = value.lower()
    if lowered in {"1", "true", "yes", "y"}:
        return True
    if lowered in {"0", "false", "no", "n"}:
        return False
    raise argparse.ArgumentTypeError("expected true or false")


def write_readme(dest: Path, manifest: dict[str, Any]) -> None:
    lines = [
        f"# {manifest['title']}",
        "",
        manifest["description"],
        "",
        "This example was captured from a user project. It is a compact reference package, not a full CCS import project.",
        "",
        "## Summary",
        "",
        f"- Board: {manifest.get('board') or 'unknown'}",
        f"- Device: {manifest.get('device') or 'unknown'}",
        f"- Complexity: {manifest.get('complexity')}",
        f"- Validation: {manifest.get('validation_level')}",
        f"- Peripherals: {', '.join(manifest.get('peripherals') or []) or 'unknown'}",
        f"- Pins: {', '.join(manifest.get('pins') or []) or 'unknown'}",
        "",
        "## Files",
        "",
        f"- `{manifest['syscfg']}`: captured SysConfig source",
        "- `src/`: selected source files",
        "- `manifest.json`: machine-readable summary for example selection",
        "",
        "## Notes",
        "",
        "- Rebuild the target project after copying patterns from this example.",
        "- Inspect the target project's generated `ti_msp_dl_config.h`; generated names may differ.",
        "- For advanced examples, copy only the relevant module pattern instead of transplanting the whole source tree.",
    ]
    dest.joinpath("README.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description="Capture a compact MSPM0 CCS example package.")
    parser.add_argument("project", type=Path, help="Source CCS project directory.")
    parser.add_argument("--name", required=True, help="Example directory name to create.")
    parser.add_argument("--title", help="Human-readable example title.")
    parser.add_argument("--description", help="Short example description.")
    parser.add_argument("--syscfg", help="Relative path to the .syscfg file if the project has more than one.")
    parser.add_argument("--include", action="append", default=[], help="Source glob to include, relative to project root. Repeatable.")
    parser.add_argument("--exclude", action="append", default=[], help="Additional glob to exclude. Repeatable.")
    parser.add_argument("--auto", action="store_true", help="Best-effort include of common source directories.")
    parser.add_argument("--board", default="", help="Board name for manifest.")
    parser.add_argument("--validated", type=bool_arg, default=False, help="Whether this example has been hardware validated.")
    parser.add_argument("--validation-level", default="unverified", help="Validation label, e.g. source, build, hardware.")
    parser.add_argument("--force", action="store_true", help="Overwrite an existing example directory.")
    parser.add_argument(
        "--examples-dir",
        type=Path,
        default=Path(__file__).resolve().parents[1] / "examples",
        help="Destination examples directory.",
    )
    args = parser.parse_args()

    project = args.project.resolve()
    if not project.exists():
        raise SystemExit(f"Project directory not found: {project}")

    dest = (args.examples_dir / args.name).resolve()
    if dest.exists():
        if not args.force:
            raise SystemExit(f"Destination exists: {dest}. Pass --force to overwrite.")
        shutil.rmtree(dest)
    dest.mkdir(parents=True)
    src_dest = dest / "src"
    src_dest.mkdir()

    syscfg = find_syscfg(project, args.syscfg)
    syscfg_text = read_text(syscfg)
    sources = select_sources(project, args.include, DEFAULT_EXCLUDES + args.exclude, args.auto)

    shutil.copy2(syscfg, dest / "example.syscfg")
    for source in sources:
        rel = source.relative_to(project)
        out = src_dest / rel
        out.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, out)

    metadata = parse_metadata(syscfg_text)
    peripherals = parse_modules(syscfg_text)
    pins = parse_pins(syscfg_text)
    freertos = source_mentions_freertos(sources)
    complexity = classify_complexity(peripherals, pins, sources, freertos)

    manifest = {
        "schema": 1,
        "name": args.name,
        "title": args.title or args.name.replace("_", " ").title(),
        "description": args.description or "Captured MSPM0 CCS example.",
        "board": args.board,
        "device": metadata.get("device") or metadata.get("part") or "",
        "package": metadata.get("package") or "",
        "product": metadata.get("product") or "",
        "sysconfig_versions": metadata.get("versions") or "",
        "validated": args.validated,
        "validation_level": args.validation_level,
        "complexity": complexity,
        "peripherals": peripherals,
        "pins": pins,
        "source_files": [f"src/{rel_posix(path, project)}" for path in sources],
        "syscfg": "example.syscfg",
        "generated_names": detect_generated_names(project),
        "tags": sorted(set(peripherals + pins + ([ "freertos" ] if freertos else []))),
    }

    (dest / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    write_readme(dest, manifest)

    print(f"Captured example: {dest}")
    print(f"Sources copied: {len(sources)}")
    print(f"Complexity: {complexity}")
    if complexity == "advanced":
        print("Note: advanced examples should be used as module references, not copied wholesale.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
