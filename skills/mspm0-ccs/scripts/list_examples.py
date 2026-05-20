#!/usr/bin/env python3
"""List packaged MSPM0 skill examples from manifest.json files."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


def load_manifest(path: Path) -> dict[str, Any]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:  # noqa: BLE001 - keep CLI diagnostics simple
        return {"name": path.parent.name, "error": str(exc)}
    if not isinstance(data, dict):
        return {"name": path.parent.name, "error": "manifest is not an object"}
    return data


def as_text(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, list):
        return ",".join(str(item) for item in value)
    return str(value)


def clock_text(manifest: dict[str, Any]) -> str:
    clock = manifest.get("clock")
    if not isinstance(clock, dict):
        return ""
    cpu = clock.get("cpuclk_hz")
    if isinstance(cpu, int):
        return f"{cpu // 1_000_000}MHz"
    return as_text(cpu)


def main() -> int:
    parser = argparse.ArgumentParser(description="List mspm0-ccs packaged examples.")
    parser.add_argument(
        "--examples-dir",
        default=Path(__file__).resolve().parents[1] / "examples",
        type=Path,
        help="Examples directory. Defaults to this skill's examples directory.",
    )
    parser.add_argument("--json", action="store_true", help="Print machine-readable JSON.")
    args = parser.parse_args()

    manifests = []
    for manifest_path in sorted(args.examples_dir.glob("*/manifest.json")):
        manifest = load_manifest(manifest_path)
        manifest["_path"] = str(manifest_path.parent)
        manifests.append(manifest)

    if args.json:
        print(json.dumps(manifests, ensure_ascii=False, indent=2))
        return 0

    if not manifests:
        print(f"No examples found under {args.examples_dir}")
        return 0

    headers = ("name", "complexity", "clock", "pins", "peripherals", "validated")
    rows = []
    for manifest in manifests:
        rows.append(
            (
                as_text(manifest.get("name") or Path(manifest.get("_path", "")).name),
                as_text(manifest.get("complexity")),
                clock_text(manifest),
                as_text(manifest.get("pins")),
                as_text(manifest.get("peripherals")),
                as_text(manifest.get("validated")),
            )
        )

    widths = [len(header) for header in headers]
    for row in rows:
        widths = [max(width, len(cell)) for width, cell in zip(widths, row)]

    print("  ".join(header.ljust(width) for header, width in zip(headers, widths)))
    print("  ".join("-" * width for width in widths))
    for row in rows:
        print("  ".join(cell.ljust(width) for cell, width in zip(row, widths)))

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
