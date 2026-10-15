# Scientific Simulation and 3D Architecture

## Educational purpose

Every 3D scene must answer a scientific question. Avoid decorative particles that do not represent a variable, process, structure, or relationship.

## Simulation specification

For each scene define:

- concept;
- variables and units;
- constants;
- valid ranges;
- equations;
- scientific assumptions;
- independent oracle;
- invariant;
- visual mapping;
- limitations;
- expected observation;
- reset state.

## Representative models

Rendered particle counts are scaled representations. State this clearly. Preserve relative relationships, not literal molecular counts.

## Real-time architecture

Separate exact science from visual interpolation:

```text
scientificState       exact calculated values
targetVisualState     visual target derived from science
currentVisualState    eased/interpolated display state
renderLoop            persistent requestAnimationFrame loop
```

Rules:

- Initialize a scene once.
- Create a renderer once.
- Keep the same canvas mounted.
- Input events update state only.
- Geometry, particles, gauges, and labels update inside the persistent loop.
- Do not reset the camera or particles on ordinary input.
- Resize only when actual dimensions change.
- Avoid duplicate animation loops and listeners.

## Particle systems

- Keep particles inside boundaries.
- Use stable wall collisions.
- Tie speed, density, color, and proportions to documented scientific quantities.
- Use object pooling or buffer geometry when useful.
- Add or remove representative particles smoothly.
- Dispose permanently removed GPU resources.

## Verification card

Every major simulation should show a live **التحقق العلمي** value: a constant product, ratio, conservation relationship, equilibrium condition, or geometric constraint relevant to the lesson.

## Fallback

When WebGL is unavailable, provide a meaningful 2D or textual state. Never leave a blank or black panel.
