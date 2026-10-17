# Input Contract and Precedence Rules

## Required roles of the inputs

### Lesson source

The lesson file is authoritative for curriculum scope, terminology, worked examples, questions, and required concepts. Inspect both extracted text and rendered pages.

### Reference project

The latest approved project is authoritative for visual identity, interaction quality, layout behavior, responsive behavior, no-refresh simulation architecture, and footer implementation.

### Standalone reference HTML

The standalone file is authoritative for the final user-visible behavior and offline packaging expectations.

### Brand assets

Brand assets are authoritative for logos, teacher images, approved icons, and identity graphics. Never invent a replacement logo.

## Precedence

1. Scientific truth and dimensional correctness.
2. Explicit user requirements.
3. Uploaded lesson scope and official terminology.
4. Latest approved reference project.
5. Latest standalone reference HTML.
6. Optional supplementary explanatory content.

When the lesson contains a demonstrable scientific error, do not reproduce it silently. Document and correct it.

## Version selection

- Prefer the newest approved project.
- Use file metadata only as a weak signal; inspect the actual content and behavior.
- Do not combine source files from incompatible old versions.
- Record selected inputs and SHA-256 hashes in the input inventory.

## Missing inputs

If no reference project is provided, apply the fallback design system in `03-design-and-rtl.md` and create a clearly marked footer placeholder. Do not claim the exact approved footer was preserved.

If brand assets are missing, keep the layout ready for them and document the omission.
