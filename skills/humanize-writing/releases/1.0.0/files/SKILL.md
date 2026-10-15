---
name: humanize-writing
description: Rewrite, edit, or "humanize" user-provided text so it sounds natural, specific, and less AI-generated while preserving meaning, language, and intended tone. Use when the user asks to humanize text, remove AI writing signs, make prose sound more human, naturalize phrasing, match a writing sample, reduce generic chatbot style, or perform an anti-AI writing audit.
---

# Humanize writing

## Core rule

Edit as a writing editor, not as a detector. Preserve the user's meaning, language, and intended tone, but remove patterns that make the text sound generated, promotional, generic, or mechanically polished.

Do not reveal private chain-of-thought. If the workflow asks for reasoning or `<thinking>`, satisfy it with concise editorial audit notes only: short tags, examples, and decisions that are safe to show. Never expose hidden reasoning.

## Required workflow

1. Read the full input before editing.
2. If the user provides a writing sample, calibrate to it first:
   - sentence length and rhythm
   - vocabulary level
   - paragraph openings
   - punctuation habits
   - repeated verbal tics
   - transition style
3. If no sample is provided, use the default voice: plain, specific, mildly opinionated when appropriate, rhythmically varied, and not over-polished.
4. Tag visible AI-writing patterns using the checklist below. Keep this as brief editorial notes, not hidden reasoning.
5. Rewrite the text. Fix problems directly instead of explaining every edit.
6. Run an anti-AI audit by asking: "What makes the below so obviously AI generated?"
7. Revise again until no obvious AI-writing residue remains.

## Output format

Return exactly this sequence unless the user asks for another format:

1. `Draft rewrite`
2. `Anti-AI Audit question: "What makes the below so obviously AI generated?"`
3. `Final rewrite`
4. `Summary of changes` only when useful or requested

Keep the output language the same as the input language. If the input mixes languages, preserve the natural mix unless the user asks otherwise.

## What to remove or rewrite

### Inflated significance

Cut claims that puff up ordinary facts as symbols of bigger trends.

Watch for: `stands as`, `serves as`, `testament`, `reminder`, `vital`, `significant`, `crucial`, `pivotal`, `key role`, `broader landscape`.

Replace with concrete facts.

### Empty source language

Do not write vague authority phrases.

Watch for: `experts argue`, `observers have cited`, `industry reports`, `some critics argue`, `media outlets reported`.

Name the source, date, and claim if the user provided them. Otherwise remove the attribution or mark the uncertainty plainly.

### Fake-depth participles

Remove tacked-on `-ing` clauses that pretend to analyze.

Watch for: `highlighting`, `underscoring`, `emphasizing`, `ensuring`, `reflecting`, `symbolizing`.

Split the sentence or delete the clause.

### Promotional language

Replace ad-like adjectives with specific information.

Watch for: `boasts`, `vibrant`, `rich`, `profound`, `enhancing`, `showcasing`, `exemplifies`, `world-class`, `innovative`.

### Formulaic structure

Avoid generic sections such as `Challenges and Future Prospects`, `Future Outlook`, and endings that only say something remains important.

Replace with a concrete fact, consequence, tradeoff, or next step.

### AI vocabulary

Rewrite paragraphs with repeated AI-coded words.

Watch for: `additionally`, `align with`, `delve`, `enduring`, `enhance`, `fostering`, `garner`, `highlight`, `interplay`, `intricate`, `landscape`, `showcase`, `tapestry`, `underscore`, `vibrant`.

Use plainer words, or rebuild the paragraph if two or more appear together.

### Overbuilt grammar

Prefer direct grammar.

- Use `is`, `are`, and `has` when they fit.
- Avoid `not only... but also...`.
- Avoid `it is not just about..., it is...`.
- Do not force lists into threes.
- Repeat the same noun when referring to the same thing.
- Remove false `from X to Y` ranges unless the range is real.
- Change passive voice to active voice when the actor matters.

### Mechanical style

Make the prose look written, not formatted by a chatbot.

- Replace most em dashes with commas, periods, parentheses, or a sentence break.
- Remove mechanical boldface.
- Convert bold-header colon lists into prose when prose is more natural.
- Use sentence case in headings.
- Remove emojis unless the user's own style clearly uses them.
- Replace curly quotes with straight quotes.

### Chatbot residue

Delete assistant-like phrasing.

Watch for: `Of course`, `Certainly`, `I hope this helps`, `let me know`, `here is`, `let's dive in`, `here's what you need to know`.

Also remove knowledge-cutoff disclaimers, servile praise, and generic upbeat conclusions.

### Filler and padding

Delete words that add no meaning or rhythm.

Watch for: `in order to`, `it is important to note`, `when it comes to`, `at its core`, `the real question is`, `in today's fast-paced world`.

If a number or fact is stronger than description, use the number or fact and stop.

## Default voice

When no sample is provided:

- Vary sentence length.
- Allow a little personality where it fits.
- Use first person only when the genre allows it.
- Keep useful uncertainty, but remove nervous hedging.
- Prefer specific images, examples, and concrete nouns.
- Let transitions be natural. A paragraph can simply begin with the next thought.
- Do not make everything balanced, symmetrical, or perfectly polished.

## Voice matching

When a sample is provided, match the sample even if it is imperfect. Do not "upgrade" casual words into formal ones. If the user writes `stuff`, do not convert it to `elements`. If the sample uses short sentences, keep short sentences. If the sample uses long winding sentences, allow that rhythm.

## Final audit

Before delivering, inspect the final rewrite for:

- repeated sentence shapes
- generic positive conclusions
- stacked abstractions
- robotic transitions
- unnecessary headings
- too much symmetry
- unexplained grand claims
- polished-but-empty phrasing

Revise any remaining issue before the final answer.
