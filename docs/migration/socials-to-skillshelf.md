# Personal socials → SkillShelf

| Source behavior | Source file | Source mechanism | SkillShelf equivalent | Adaptation | Preservation test | Limitation |
|---|---|---|---|---|---|---|
| Seven factual destinations | `src/data/socials.ts` | React data array | static semantic anchors | URLs/order/labels preserved verbatim | exact-data site test | Link ownership/reachability not asserted |
| Brand icons/cards | `SocialIcon.tsx`, page/CSS imports | React + inline SVG | text-forward archive cards | Recognizable purpose; stronger focus and safe `noopener` | seven-card/focus metadata checks | Runtime SVG icons not copied |
| SEO/profile metadata | `socials/index.html` | canonical/OG/JSON-LD | SkillShelf GitHub Pages URLs | Preserve person facts and `en-ZA`; update host URLs | site metadata test | External OG caches update asynchronously |
