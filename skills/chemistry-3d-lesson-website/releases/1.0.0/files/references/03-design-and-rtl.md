# Design System, RTL, Mobile, and Footer Rules

## Identity

Preserve the approved **الطيف في الكيمياء** design language from the reference project.

Fallback palette when no reference exists:

- Deep navy `#0B1F3A`
- Primary blue `#174EA6`
- Medium blue `#2563EB`
- Cyan `#38BDF8`
- Light cyan `#EAF7FF`
- White `#FFFFFF`
- Neutral background `#F5F8FC`
- Dark text `#10243E`

Functional colors may indicate success, warning, or error. Do not replace the identity with a generic neon or purple theme.

## Desktop

Desktop must be designed for classroom presentation:

- clear top navigation and progress;
- large readable typography;
- main content and scientific simulation visible together when useful;
- sticky or semi-sticky laboratory panel;
- full-screen simulation mode;
- direct section navigation;
- pause, resume, and reset controls.

## Mobile

Mobile is not a scaled desktop page. It must include:

- no horizontal page overflow;
- touch targets around 44 px or larger;
- comfortable sliders;
- collapsible section navigation;
- expandable simulation panel;
- safe-area handling;
- portrait and landscape support;
- optional bottom navigation: المجسم، الشرح، المحاور، الاختبار;
- preserved simulation state during collapse, expansion, full screen, and rotation.

## RTL and mixed content

- Set the page and Arabic components to `dir="rtl"`.
- Set equations, variables, units, and chemical formulas to isolated `dir="ltr"` containers.
- Use structural direction rules instead of hidden Unicode bidi controls.
- Test negative signs, decimals, parentheses, subscripts, superscripts, and mixed Arabic/Latin lines.
- Reject malformed PDF/OCR glyphs and replacement characters.

## Equations

Use local KaTeX, local MathJax, or accessible semantic markup. Do not use external CDNs in the standalone build. Long equations must scroll or scale inside their own container rather than overflow the page.

## Footer lock

The approved footer is immutable. Wrap it with:

```html
<!-- FOOTER_LOCK_START -->
...approved footer...
<!-- FOOTER_LOCK_END -->
```

Generate and verify a normalized fingerprint with `scripts/footer_lock.py`.
