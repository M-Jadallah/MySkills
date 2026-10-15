# Mandatory Testing and Release Gate

## Principle

The first working build is a test candidate. Testing must be executed against the actual output. Written checklists and fabricated counts are unacceptable.

## Scientific validation

- Use an independent oracle, separate from production functions.
- Compare full-precision expected and actual values.
- Record absolute and relative error.
- Default relative tolerance: `1e-6`, unless justified.
- Validate equations, units, constants, examples, answer keys, and invariants.
- Run minimum, midpoint, maximum, intermediate, and randomized cases.
- For each major equation, target at least 50 valid random cases and invalid boundary cases.

## No-refresh regression

For every control:

- move slowly, rapidly, and repeatedly;
- verify the same canvas DOM object remains mounted;
- verify renderer creation count does not increase;
- verify scene initialization count does not increase;
- verify camera and particles do not reset unexpectedly;
- verify values and visuals update during movement;
- verify no white, black, or blank frame appears.

## Browser and responsive tests

Desktop:

- 1024x768
- 1280x720
- 1366x768
- 1440x900
- 1920x1080

Mobile portrait:

- 360x800
- 375x812
- 390x844
- 412x915
- 430x932

Mobile landscape:

- 800x360
- 812x375
- 844x390
- 915x412
- 932x430

Fail unexplained page overflow when:

```js
document.documentElement.scrollWidth > document.documentElement.clientWidth
```

Explicit equation/data scrollers are allowed.

## Accessibility

Test semantic headings, labels, accessible names, keyboard operation, focus order, contrast, reduced motion, pause controls, alt text, and textual summaries of scientific states.

## Performance and memory

Run a minimum three-minute stress test while changing controls, switching sections, resizing, pausing, resuming, and using full screen. Check FPS, input latency, duplicate loops/listeners, and persistent memory growth.

## Offline test

Disable the network and open the standalone HTML directly. Verify all images, icons, equations, scripts, simulations, assessment, branding, and footer.

## Fix-retest loop

Every failure requires:

1. record;
2. root-cause analysis;
3. fix;
4. regression test;
5. related retest;
6. full-suite retest before release.

## Release blockers

Do not release with:

- incorrect science or units;
- visual/numerical disagreement;
- canvas replacement or scene recreation during input;
- mobile overflow or hidden controls;
- broken offline assets;
- modified locked footer;
- uncaught console errors;
- missing required reports;
- unreported unexecuted tests.
