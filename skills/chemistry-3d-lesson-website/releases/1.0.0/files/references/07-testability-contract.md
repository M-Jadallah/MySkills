# Testability Contract

The generated site must expose stable semantic hooks so automated tests do not depend on fragile CSS classes.

## Required attributes

```html
<section data-lesson-section="stable-section-id">
<div data-science-sim="stable-simulation-id">
<canvas data-simulation-canvas="stable-simulation-id">
<input data-control-id="stable-control-id" data-scientific-variable="P">
<div data-verification-card="stable-simulation-id">
<nav data-mobile-nav>
<div data-final-assessment>
```

Every interactive control must have an associated visible label or accessible name.

## Debug instrumentation

Expose test-only counters in development/test builds:

```js
window.__SCIENCE_DEBUG__ = {
  sceneInitCount: {},
  rendererCreateCount: {},
  activeAnimationLoops: 0,
  lastState: {},
};
```

Increment counters only when the corresponding resource is actually created. The Playwright suite uses them to detect regressions.

## Footer markers

Use exact HTML comments:

```html
<!-- FOOTER_LOCK_START -->
<!-- FOOTER_LOCK_END -->
```

## Accessibility state summary

Each simulation must expose a readable summary, for example:

```html
<p data-simulation-summary aria-live="polite">...</p>
```

The summary should describe current variables, the observed effect, and the invariant without flooding screen readers during rapid slider movement.
