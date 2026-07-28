---
name: codex-design-intelligence
description: "Design, redesign, critique, audit, polish, harden, or translate interfaces with two preserved engines: Impeccable for product/UX/accessibility/production quality and Taste for anti-generic visual expression. Use for web, app, dashboard, image-to-code, brand-kit, layout, typography, motion, or visual QA work."
---

# Codex Design Intelligence

Keep the engines separate. Impeccable governs product context and production correctness; Taste governs visual character. Read `references/design-authority-matrix.md` before combining rules.

## Start

1. Inspect the product, stack, existing design system, content, and user constraints.
2. Select a surface mode: **Persuade**, **Operate**, **Read**, or **Experience**.
3. Set `DESIGN_VARIANCE`, `MOTION_INTENSITY`, and `VISUAL_DENSITY` from 1–10. Accessibility and reduced motion can cap these values.
4. Route the intent:
   - `init`, `shape`, `critique`, `audit`, `polish`, `distill`, `harden`, `onboard`, `animate`, `colorize`, `typeset`, `layout`, `delight`, `adapt`, `optimize` → Impeccable module of the same or closest name.
   - `design`, `redesign`, `bolder`, `quieter`, visual-language selection → Taste v2 plus Impeccable structure.
   - `image-to-code` → Taste image-to-code, then Impeccable accessibility and hardening.
   - `brand-kit` → Taste brandkit, then Impeccable context/extraction.
5. Implement in the existing stack. Do not invent dependency installation, simulated executions, unsupported functionality, or unstable placeholder assets.
6. Run one bounded consolidated review: Impeccable technical/UX audit plus Taste visual-slop audit. Return one severity-ranked defect list.

## Engine locations

- Impeccable: `../../vendor/impeccable/impeccable/`
- Taste: `../../vendor/taste-skill/skills/`

Read the selected engine module completely, including its directly referenced files. Never flatten both engines into a new generic prompt.
