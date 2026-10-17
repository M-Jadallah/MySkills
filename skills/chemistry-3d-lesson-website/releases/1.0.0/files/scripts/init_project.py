#!/usr/bin/env python3
"""Initialize a working project that follows the chemistry lesson skill contract."""

from __future__ import annotations

import argparse
import json
import shutil
from pathlib import Path

DEFAULT_DIRS = [
    "src/content",
    "src/science",
    "src/simulations",
    "src/ui",
    "src/accessibility",
    "public/assets",
    "tests/unit",
    "tests/e2e",
    "reports",
    "screenshots/desktop",
    "screenshots/mobile",
    "dist",
    "release",
]

REPORTS = [
    "TEST_PLAN.md",
    "SCIENTIFIC_VALIDATION_REPORT.md",
    "FUNCTIONAL_TEST_REPORT.md",
    "RESPONSIVE_TEST_REPORT.md",
    "ACCESSIBILITY_REPORT.md",
    "PERFORMANCE_REPORT.md",
    "CODE_QUALITY_REPORT.md",
    "SOURCE_CORRECTIONS.md",
]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", required=True, help="Project directory to create")
    parser.add_argument("--config-template", help="Optional project-config JSON template")
    parser.add_argument("--force", action="store_true", help="Allow initialization in a non-empty directory")
    args = parser.parse_args()

    root = Path(args.output).resolve()
    if root.exists() and any(root.iterdir()) and not args.force:
        parser.error(f"Output directory is not empty: {root}. Use --force to continue.")
    root.mkdir(parents=True, exist_ok=True)

    for directory in DEFAULT_DIRS:
        (root / directory).mkdir(parents=True, exist_ok=True)

    for report in REPORTS:
        report_path = root / "reports" / report
        if not report_path.exists():
            report_path.write_text(f"# {report.removesuffix('.md').replace('_', ' ')}\n\n", encoding="utf-8")

    content_map = root / "lesson-content-map.json"
    if not content_map.exists():
        content_map.write_text(
            json.dumps({"lesson": {}, "sections": []}, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )

    interaction_map = root / "interaction-map.json"
    if not interaction_map.exists():
        interaction_map.write_text(json.dumps({"simulations": []}, indent=2) + "\n", encoding="utf-8")

    config_target = root / "project-config.json"
    if args.config_template:
        shutil.copy2(Path(args.config_template), config_target)
    elif not config_target.exists():
        config_target.write_text(
            json.dumps(
                {
                    "skill_version": "1.0.0",
                    "project_name": root.name,
                    "paths": {
                        "project_root": ".",
                        "build_dir": "dist",
                        "standalone_html": "dist/lesson-standalone.html",
                        "content_map": "lesson-content-map.json",
                        "interaction_map": "interaction-map.json",
                        "reports_dir": "reports",
                        "screenshots_dir": "screenshots",
                        "footer_lock": "templates/footer-lock.json",
                    },
                    "quality_gate": {
                        "required_files": [
                            "README.md",
                            "lesson-content-map.json",
                            "interaction-map.json",
                            "dist/lesson-standalone.html",
                        ],
                        "strict_rtl": True,
                        "fail_on_remote_urls": True,
                        "fail_on_missing_assets": True,
                        "commands": [],
                    },
                },
                ensure_ascii=False,
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )

    readme = root / "README.md"
    if not readme.exists():
        readme.write_text(
            "# مشروع درس كيمياء تفاعلي\n\n"
            "هذا المجلد مُنشأ وفق مهارة chemistry-3d-lesson-website.\n\n"
            "ابدأ بإكمال `lesson-content-map.json` و`interaction-map.json` ثم نفّذ اختبارات بوابة الجودة.\n",
            encoding="utf-8",
        )

    print(f"Initialized project at: {root}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
