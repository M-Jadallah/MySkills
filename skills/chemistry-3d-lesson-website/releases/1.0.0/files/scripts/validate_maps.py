#!/usr/bin/env python3
"""Validate content and interaction maps without external dependencies."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


def require(obj: dict[str, Any], key: str, context: str, errors: list[str]) -> Any:
    if key not in obj:
        errors.append(f"{context}: missing required key '{key}'")
        return None
    return obj[key]


def validate_content_map(data: Any) -> list[str]:
    errors: list[str] = []
    if not isinstance(data, dict):
        return ["content map must be a JSON object"]
    lesson = require(data, "lesson", "content map", errors)
    sections = require(data, "sections", "content map", errors)
    if isinstance(lesson, dict):
        for key in ["id", "title_ar", "main_idea_ar", "learning_outcomes_ar"]:
            require(lesson, key, "lesson", errors)
    if not isinstance(sections, list) or not sections:
        errors.append("content map: 'sections' must be a non-empty array")
        return errors
    seen: set[str] = set()
    required = [
        "id",
        "title_ar",
        "objective_ar",
        "explanation_ar",
        "terms",
        "equations",
        "interaction",
        "verification",
        "accessibility_summary_ar",
    ]
    for index, section in enumerate(sections):
        context = f"sections[{index}]"
        if not isinstance(section, dict):
            errors.append(f"{context}: must be an object")
            continue
        for key in required:
            require(section, key, context, errors)
        section_id = section.get("id")
        if isinstance(section_id, str):
            if section_id in seen:
                errors.append(f"{context}: duplicate id '{section_id}'")
            seen.add(section_id)
        if not isinstance(section.get("explanation_ar"), list) or not section.get("explanation_ar"):
            errors.append(f"{context}: explanation_ar must be a non-empty array")
    return errors


def validate_interaction_map(data: Any) -> list[str]:
    errors: list[str] = []
    if not isinstance(data, dict):
        return ["interaction map must be a JSON object"]
    simulations = require(data, "simulations", "interaction map", errors)
    if not isinstance(simulations, list) or not simulations:
        errors.append("interaction map: 'simulations' must be a non-empty array")
        return errors
    seen: set[str] = set()
    required = ["id", "section_id", "scientific_model", "controls", "outputs", "invariant", "reset_state"]
    for index, simulation in enumerate(simulations):
        context = f"simulations[{index}]"
        if not isinstance(simulation, dict):
            errors.append(f"{context}: must be an object")
            continue
        for key in required:
            require(simulation, key, context, errors)
        sim_id = simulation.get("id")
        if isinstance(sim_id, str):
            if sim_id in seen:
                errors.append(f"{context}: duplicate id '{sim_id}'")
            seen.add(sim_id)
        controls = simulation.get("controls")
        if not isinstance(controls, list) or not controls:
            errors.append(f"{context}: controls must be a non-empty array")
        else:
            control_ids: set[str] = set()
            for c_index, control in enumerate(controls):
                c_context = f"{context}.controls[{c_index}]"
                if not isinstance(control, dict):
                    errors.append(f"{c_context}: must be an object")
                    continue
                for key in ["id", "label_ar", "variable", "unit", "min", "max", "step", "default"]:
                    require(control, key, c_context, errors)
                control_id = control.get("id")
                if isinstance(control_id, str):
                    if control_id in control_ids:
                        errors.append(f"{c_context}: duplicate control id '{control_id}'")
                    control_ids.add(control_id)
                numeric = [control.get(key) for key in ["min", "max", "step", "default"]]
                if all(isinstance(value, (int, float)) for value in numeric):
                    min_value, max_value, step, default = numeric
                    if min_value >= max_value:
                        errors.append(f"{c_context}: min must be lower than max")
                    if step <= 0:
                        errors.append(f"{c_context}: step must be positive")
                    if not min_value <= default <= max_value:
                        errors.append(f"{c_context}: default must be within min/max")
    return errors


def load(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise SystemExit(f"Cannot read {path}: {exc}") from exc


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--content-map", required=True)
    parser.add_argument("--interaction-map", required=True)
    args = parser.parse_args()

    errors = []
    errors.extend(validate_content_map(load(Path(args.content_map))))
    errors.extend(validate_interaction_map(load(Path(args.interaction_map))))

    if errors:
        print("Map validation failed:")
        for error in errors:
            print(f"- {error}")
        return 1
    print("Content and interaction maps are valid.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
