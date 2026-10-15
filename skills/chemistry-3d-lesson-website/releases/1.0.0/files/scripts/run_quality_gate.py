#!/usr/bin/env python3
"""Run the static quality gate and configured project commands."""

from __future__ import annotations

import argparse
import json
import os
import shlex
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from common import load_json, write_json


SCRIPT_DIR = Path(__file__).resolve().parent


def run_command(name: str, command: list[str], cwd: Path, optional: bool = False) -> dict[str, Any]:
    started = time.perf_counter()
    try:
        process = subprocess.run(
            command,
            cwd=cwd,
            text=True,
            capture_output=True,
            check=False,
            env=os.environ.copy(),
        )
        return {
            "name": name,
            "command": command,
            "cwd": str(cwd),
            "optional": optional,
            "status": "passed" if process.returncode == 0 else ("skipped" if optional and process.returncode == 127 else "failed"),
            "returncode": process.returncode,
            "duration_seconds": round(time.perf_counter() - started, 3),
            "stdout": process.stdout,
            "stderr": process.stderr,
        }
    except FileNotFoundError as exc:
        return {
            "name": name,
            "command": command,
            "cwd": str(cwd),
            "optional": optional,
            "status": "skipped" if optional else "failed",
            "returncode": 127,
            "duration_seconds": round(time.perf_counter() - started, 3),
            "stdout": "",
            "stderr": str(exc),
        }


def script_command(name: str, script: str, args: list[str], cwd: Path, optional: bool = False) -> dict[str, Any]:
    return run_command(name, [sys.executable, str(SCRIPT_DIR / script), *args], cwd, optional)


def markdown_report(results: list[dict[str, Any]], generated_at: str) -> str:
    passed = sum(item["status"] == "passed" for item in results)
    failed = sum(item["status"] == "failed" for item in results)
    skipped = sum(item["status"] == "skipped" for item in results)
    lines = [
        "# Quality Gate Report",
        "",
        f"Generated: {generated_at}",
        "",
        f"- Passed: {passed}",
        f"- Failed: {failed}",
        f"- Skipped: {skipped}",
        "",
        "| Check | Status | Return code | Duration (s) |",
        "|---|---|---:|---:|",
    ]
    for item in results:
        lines.append(f"| {item['name']} | {item['status']} | {item['returncode']} | {item['duration_seconds']} |")
    lines.extend(["", "## Details", ""])
    for item in results:
        lines.extend(
            [
                f"### {item['name']}",
                "",
                f"- Status: `{item['status']}`",
                f"- Command: `{shlex.join(item['command'])}`",
                f"- Working directory: `{item['cwd']}`",
                "",
            ]
        )
        if item["stdout"].strip():
            lines.extend(["**stdout**", "", "```text", item["stdout"].rstrip(), "```", ""])
        if item["stderr"].strip():
            lines.extend(["**stderr**", "", "```text", item["stderr"].rstrip(), "```", ""])
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", required=True)
    args = parser.parse_args()

    config_path = Path(args.config).resolve()
    config = load_json(config_path)
    project_root = (config_path.parent / config.get("paths", {}).get("project_root", ".")).resolve()
    paths = config.get("paths", {})
    quality = config.get("quality_gate", {})
    reports_dir = (project_root / paths.get("reports_dir", "reports")).resolve()
    reports_dir.mkdir(parents=True, exist_ok=True)

    results: list[dict[str, Any]] = []

    required_files = quality.get("required_files", [])
    missing = [str(project_root / item) for item in required_files if not (project_root / item).exists()]
    results.append(
        {
            "name": "required-files",
            "command": ["internal", "required-files"],
            "cwd": str(project_root),
            "optional": False,
            "status": "passed" if not missing else "failed",
            "returncode": 0 if not missing else 1,
            "duration_seconds": 0.0,
            "stdout": "All required files exist." if not missing else "",
            "stderr": "\n".join(missing),
        }
    )

    content_map = project_root / paths.get("content_map", "lesson-content-map.json")
    interaction_map = project_root / paths.get("interaction_map", "interaction-map.json")
    results.append(
        script_command(
            "map-validation",
            "validate_maps.py",
            ["--content-map", str(content_map), "--interaction-map", str(interaction_map)],
            project_root,
        )
    )

    build_dir = project_root / paths.get("build_dir", "dist")
    if quality.get("strict_rtl", True):
        results.append(
            script_command(
                "rtl-unicode-audit",
                "check_rtl_unicode.py",
                ["--path", str(build_dir), "--fail-on-found"],
                project_root,
            )
        )

    offline_args = ["--path", str(build_dir)]
    if quality.get("fail_on_remote_urls", True):
        offline_args.append("--fail-on-remote")
    if quality.get("fail_on_missing_assets", True):
        offline_args.append("--fail-on-missing")
    results.append(script_command("offline-assets", "check_offline_assets.py", offline_args, project_root))

    footer_lock = project_root / paths.get("footer_lock", "templates/footer-lock.json")
    standalone = project_root / paths.get("standalone_html", "dist/lesson-standalone.html")
    if standalone.exists():
        results.append(
            script_command(
                "dom-contract",
                "check_dom_contract.py",
                ["--html", str(standalone)],
                project_root,
            )
        )

    if footer_lock.exists() and standalone.exists():
        results.append(
            script_command(
                "footer-lock",
                "footer_lock.py",
                ["verify", "--html", str(standalone), "--lock", str(footer_lock)],
                project_root,
            )
        )
    else:
        results.append(
            {
                "name": "footer-lock",
                "command": ["internal", "footer-lock"],
                "cwd": str(project_root),
                "optional": False,
                "status": "failed",
                "returncode": 1,
                "duration_seconds": 0.0,
                "stdout": "",
                "stderr": f"Missing footer lock or standalone HTML: {footer_lock}, {standalone}",
            }
        )

    for item in quality.get("commands", []):
        name = item.get("name", "unnamed-command")
        command = item.get("command")
        if not isinstance(command, list) or not command:
            results.append(
                {
                    "name": name,
                    "command": [],
                    "cwd": str(project_root),
                    "optional": bool(item.get("optional", False)),
                    "status": "failed",
                    "returncode": 2,
                    "duration_seconds": 0.0,
                    "stdout": "",
                    "stderr": "Configured command must be a non-empty array.",
                }
            )
            continue
        cwd = (project_root / item.get("cwd", ".")).resolve()
        results.append(run_command(name, [str(part) for part in command], cwd, bool(item.get("optional", False))))

    generated_at = datetime.now(timezone.utc).isoformat()
    report = {
        "generated_at": generated_at,
        "config": str(config_path),
        "project_root": str(project_root),
        "results": results,
        "summary": {
            "passed": sum(item["status"] == "passed" for item in results),
            "failed": sum(item["status"] == "failed" for item in results),
            "skipped": sum(item["status"] == "skipped" for item in results),
        },
    }
    write_json(reports_dir / "QUALITY_GATE.json", report)
    (reports_dir / "QUALITY_GATE.md").write_text(markdown_report(results, generated_at), encoding="utf-8")

    for result in results:
        print(f"[{result['status'].upper():7}] {result['name']}")

    return 1 if report["summary"]["failed"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
