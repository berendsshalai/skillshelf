# Vercel Find Skills → Codex

| Source behavior | Source file | Source mechanism | Codex equivalent | Adaptation | Preservation test | Limitation |
|---|---|---|---|---|---|---|
| Search before reinvention | `skills/find-skills/SKILL.md` | `npx skills find` | Installed plugins/skills plus trusted registry/source search | Keep search; add immutable pin and licence/security review | Discovery scenario requires search and no blind install | Registry popularity is not trust |
| Offer installation | same | global `npx ... -g -y` | Codex marketplace or `.agents/skills` | Separate reviewed recommendation from explicit install scope | Negative test rejects title-only/global `-y` | External registry can be unavailable |
| Judge quality | same | installs, stars, reputation | Commit/licence/activity/compatibility evidence | Security and licence can block popularity | Contract assertions | Maintainer intent can remain uncertain |
