# Deep Lesson Analysis Workflow

## Goal

Transform the source lesson into a complete instructional model before coding.

## Extraction checklist

Extract and validate:

- title, main idea, and learning outcomes;
- definitions and terminology;
- laws, equations, constants, symbols, and units;
- assumptions and conditions;
- direct and inverse relationships;
- microscopic and macroscopic explanations;
- experiments, apparatus, observations, and conclusions;
- charts, diagrams, tables, figures, and captions;
- worked examples and intermediate calculations;
- verification questions and review questions;
- multiple-choice questions and answer keys;
- real-world applications;
- common misconceptions;
- prerequisite knowledge and concept dependencies.

## Visual inspection

Render and inspect all pages. Parsed text is not sufficient for:

- equations and fractions;
- chemical subscripts and superscripts;
- scientific diagrams;
- charts and apparatus;
- callouts and labels;
- layout-dependent meaning.

## Content-map rules

Each section record must include:

- stable ID;
- Arabic title;
- objective;
- explanation sequence;
- terms;
- equations;
- visual source references;
- interaction concept;
- controls;
- invariant;
- example;
- quick check;
- misconception;
- accessibility summary.

Validate against `templates/lesson-content-map.schema.json`.

## Interaction-map rules

Each control record must include:

- stable control ID;
- section ID;
- scientific variable and unit;
- minimum, maximum, step, and default;
- validation rules;
- exact numerical outputs;
- visual outputs;
- constants that must remain unchanged;
- reset behavior;
- invalid-input response.

Validate against `templates/interaction-map.schema.json`.

## Source corrections

Create `source-corrections.md` with:

- source location;
- original content;
- issue;
- correction;
- scientific basis;
- implementation impact.

Do not silently alter official wording when no scientific correction is needed.
