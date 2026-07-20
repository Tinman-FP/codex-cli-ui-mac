# Localization And Layout QA Checklist

Use this before promoting localization and culture items from `REVIEW` or `PARTIAL` to `PASS`.

## Long Text

- Run controls remain one row and scroll horizontally when labels are longer than English.
- Sidebar, project names, thread titles, file names, and deliverable labels do not overlap adjacent controls.
- Long file paths and technical identifiers wrap without hiding the clickable target.

## RTL And Mixed Direction Text

- Chat messages remain readable when the document or a message uses `dir="rtl"`.
- Composer, run controls, and engineering controls keep logical ordering and do not overlap.
- Technical identifiers, file paths, commands, product names, part numbers, and proper nouns are preserved unless the user asks for translated labels.

## Locale-Sensitive Answers

- Dates that can mean month/day/year or day/month/year are called out as ambiguous.
- Time zones are explicit for logs, schedules, aviation, and machine events.
- Currency, taxes, shipping, duties, and region-specific availability are stated as assumptions.
- Legal, policy, electrical code, aviation, tax, and safety caveats name the jurisdiction boundary instead of pretending one region applies everywhere.

## Culture And Language Meaning

- Examples should be neutral, work-relevant, and easy to replace when the user gives a country, community, customer, or workplace context.
- Do not use jokes, stereotypes, mock accents, identity-based assumptions, or culturally loaded examples unless the user explicitly supplies that context and it is respectful.
- Names from different cultures are preserved exactly as written, including accents, capitalization, spacing, hyphens, patronymics, family-name order, and particles such as `de`, `van`, `bin`, or `al`.
- When sorting, deduplicating, or formatting names, keep the original display name and ask before changing order or shortening it.
- Idioms are translated by meaning first, not word-for-word; if an idiom may not carry across languages, explain the intended meaning and give a plain-language equivalent.
- Multilingual documents keep source language, target language, technical terms, names, file paths, part numbers, and units visible unless the user asks for a localized final-only version.
- If a translation or cultural interpretation is uncertain, state the uncertainty and ask for audience, region, tone, and formality instead of guessing.

## Accessibility Preferences

- Reduced-motion mode removes animation and transition timing.
- Keyboard and screen-reader paths still work when translated labels are longer.
- User preference requests, such as simpler wording or screen-reader-friendly summaries, are treated as task constraints.
