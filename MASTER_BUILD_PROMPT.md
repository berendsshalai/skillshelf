# CODEX MASTER BUILD PROMPT

## Project

**Repository name:** `skillshelf`
**GitHub target:** `berendsshalai/skillshelf`
**Product name:** `SkillShelf`
**Primary platform:** OpenAI Codex
**Repository visibility:** Public
**Primary operating system:** Windows
**Author:** Sha-Lai Berends
**GitHub account:** `berendsshalai`

---

# 1. MASTER ROLE

Act as the:

* Codex Master Builder
* AI Systems Architect
* Agent-Skills Architect
* Codex Plugin Engineer
* Prompt Engineer
* MCP Integration Engineer
* Open-Source Migration Engineer
* Licence and Attribution Auditor
* Context-Economy Engineer
* Multi-Agent Orchestrator
* Test Director
* GitHub Release Engineer
* Documentation Owner
* Frontend Design Director
* Security Reviewer
* Final Release Authority

You are not producing examples, fragments, proposals, or pseudocode.

You must inspect, acquire, preserve, adapt, improve, test, document, package, publish, and validate a complete Codex-first skills repository named:

```text
berendsshalai/skillshelf
```

The finished repository must operate as:

1. A public skills library.
2. A Codex-native plugin or marketplace package.
3. A provenance-preserving collection of upgraded open-source skills.
4. A reusable agent architecture.
5. A documented MCP integration architecture.
6. A GitHub Pages documentation and socials site.
7. A synchronisable downstream derivative that can track upstream changes.
8. A working personal skill shelf for Sha-Lai Berends.

Do not stop after scaffolding.

Do not leave placeholder implementations.

Do not produce empty agents, decorative skills, fake MCP configurations, incomplete tests, or documentation that claims unsupported functionality.

Continue until the local repository is complete, tests pass, the GitHub repository exists, the source is pushed, and the final handoff is written.

---

# 2. USER AUTHORITY

The user explicitly authorises you to:

* Create the public GitHub repository `berendsshalai/skillshelf` if it does not exist.
* Create the local project directory.
* Initialise Git.
* Add source files.
* Add upstream repositories as submodules where appropriate.
* Create tracked source snapshots.
* Create branches.
* Commit project files.
* Push the completed repository.
* Configure GitHub Pages.
* Create GitHub Actions workflows.
* Open a pull request when an existing repository requires protected modification.
* Create Codex skills, agents, plugin manifests, scripts, tests, documentation, and example MCP configuration.

This authority does not permit you to:

* Force-push over existing history.
* Delete unrelated user repositories.
* overwrite an existing repository without inventory and backup.
* Publish secrets.
* commit authentication tokens.
* change upstream repositories.
* falsely claim authorship of upstream work.
* remove upstream licence notices.
* weaken source attribution.
* silently alter global Codex configuration.
* silently install untrusted MCP servers.
* copy content whose redistribution terms cannot be verified.

---

# 3. TARGET LOCATION

Resolve the local root as follows:

1. If the current directory is already an existing checkout of `berendsshalai/skillshelf`, use it.
2. If the current directory is an empty folder named `skillshelf`, use it.
3. Otherwise, on Windows use:

```powershell
$PROJECT_ROOT = Join-Path $env:USERPROFILE "Desktop\skillshelf"
```

4. On Linux, macOS, or WSL use:

```bash
PROJECT_ROOT="$HOME/skillshelf"
```

Do not hardcode a Windows username.

Before changing an existing target:

```text
inventory
→ inspect Git state
→ inspect remotes
→ create timestamped backup
→ create a working branch
→ modify
```

If the repository is new, initialise it with `main` as the default branch.

---

# 4. SOURCE REGISTRY

Use the following upstream sources.

## Source A — Find Skills

```text
https://github.com/vercel-labs/skills
```

Primary skill:

```text
skills/find-skills/SKILL.md
```

Purpose:

* Discover existing agent skills.
* Verify skill quality.
* Install suitable skills.
* Prevent unnecessary reinvention.

## Source B — Superpowers

```text
https://github.com/obra/superpowers
```

Purpose:

* Brainstorming.
* Planning.
* Test-driven development.
* Systematic debugging.
* Worktree isolation.
* Parallel-agent development.
* Code review.
* Verification before completion.
* Branch completion.
* Skill authoring.

## Source C — Persistent Memory

```text
https://github.com/thedotmack/claude-mem
```

Purpose:

* Persistent cross-session memory.
* Observation capture.
* Summarisation.
* Progressive disclosure.
* Search, timeline, and detailed retrieval.
* SQLite and vector-backed retrieval.
* MCP memory search.
* Session context restoration.

This repository already contains Codex-related implementation. Inspect and improve its current Codex path rather than treating it as Claude-only.

## Source D1 — Impeccable

```text
https://github.com/pbakaus/impeccable
```

Purpose:

* Production-grade interface design.
* UX strategy.
* Visual hierarchy.
* Accessibility.
* Responsive behaviour.
* Typography.
* Motion.
* Design-system extraction.
* UI critique, audit, polish, hardening, and optimisation.

Inspect its existing `.agents/skills/` and plugin-compatible surfaces before performing any migration.

## Source D2 — Taste Skill

```text
https://github.com/leonxlnx/taste-skill
```

Purpose:

* Anti-generic frontend design.
* High visual quality.
* Layout variance.
* Motion direction.
* Density control.
* Image-to-code workflows.
* Redesign workflows.
* Codex/GPT-oriented design constraints.
* Full-output enforcement.
* Visual-design specialisations.

## Source E — Skill Governance

```text
https://github.com/rebelytics/one-skill-to-rule-them-all
```

Purpose:

* Observe substantive task execution.
* Detect missing skill coverage.
* Capture reusable methodology.
* Improve skills from real usage evidence.
* Maintain cross-cutting principles.
* Stage reviewed improvements.
* Protect live skills from unsafe autonomous modification.

## Codex Compatibility Authorities

Use current official Codex documentation and repositories as the platform authority:

```text
https://github.com/openai/skills
https://github.com/openai/plugins
https://github.com/openai/codex
```

Use the current official `migrate-to-codex` skill where available.

## Personal UI Source

Use the socials implementation from:

```text
https://github.com/berendsshalai/berendsshalai-project-systemtoportfolio
```

At minimum inspect:

```text
socials/index.html
src/data/socials.ts
src/components/SocialIcon.tsx
src/data/socials.test.ts
```

Trace all imports, styles, assets, routes, and build dependencies before copying or extracting the page.

---

# 5. SOURCE-OF-TRUTH PRECEDENCE

Use this precedence order:

```text
1. User requirements in this prompt
2. Current official OpenAI Codex schemas and documentation
3. Current upstream repository implementation
4. Existing outputs and architecture described in this prompt
5. Your implementation judgment
```

Behavioural source of truth:

```text
upstream skill content
```

Codex packaging source of truth:

```text
current official Codex specifications
```

Licence source of truth:

```text
the exact licence and notices at the pinned upstream commit
```

Do not assume a repository’s licence from memory.

Do not assume a file path still exists.

Do not assume a Claude hook has a direct Codex equivalent.

Do not invent Codex manifest fields, agent fields, hook names, MCP declarations, or plugin commands.

Inspect and validate the current format first.

---

# 6. NON-NEGOTIABLE PRESERVATION RULE

The upstream skills must not be:

* Summarised into shallow prompts.
* Reduced to a few generic instructions.
* Flattened into one oversized `SKILL.md`.
* Rewritten from memory.
* Stripped of scripts.
* Stripped of references.
* Stripped of supporting assets.
* Stripped of testing methodology.
* Stripped of trigger rules.
* Stripped of edge cases.
* Stripped of safety rules.
* Stripped of provenance.
* Combined in a way that creates contradictory behaviour.
* Rebranded as wholly original work.
* Made dependent on Claude.
* Made weaker for the sake of uniformity.

Adaptation must be additive and measurable.

Use:

```text
preserve
→ map
→ adapt
→ extend
→ test
→ compare
```

Never use:

```text
summarise
→ rename
→ publish
```

---

# 7. FIVE TOP-LEVEL SKILLS

The final Codex plugin must expose exactly five top-level SkillShelf skills.

```text
1. find-skills-codex
2. superpowers-codex
3. codex-memory
4. codex-design-intelligence
5. codex-skill-governor
```

Each top-level skill may contain internal references, scripts, modules, tests, and preserved sub-workflows.

Do not expose dozens of uncoordinated skills without a routing layer.

Do not erase upstream sub-skills. Preserve them as internal modules and allow the parent skill to load them on demand.

---

# 8. SKILL 1 — FIND SKILLS CODEX

Create:

```text
skills/find-skills-codex/
```

Required contents:

```text
SKILL.md
README.md
references/
scripts/
tests/
PROVENANCE.yml
SEMANTIC_CONTRACT.yml
UPSTREAM_DIFF.md
```

Required behaviour:

1. Detect when the requested task may already have an installable skill.
2. Identify the domain and exact task.
3. Search trusted skill indexes.
4. Inspect the source repository.
5. Verify:

   * licence;
   * maintainership;
   * installation count where available;
   * repository activity;
   * source reputation;
   * security concerns;
   * supported platforms;
   * Codex compatibility.
6. Prefer existing high-quality skills over creating duplicates.
7. Generate Codex installation instructions.
8. Use GitHub or source-control MCP access when available.
9. Never install a skill based only on a search-result title.
10. Never execute arbitrary install scripts without inspection.
11. Route Claude-oriented skills through the Codex migration process.
12. Record the selected source commit and licence.
13. Fall back to direct execution or local skill creation only after a real search fails.

Enhance the source with:

* Codex-specific installation detection.
* Plugin marketplace support.
* MCP-supported repository inspection.
* Security scoring.
* Licence validation.
* Compatibility reporting.
* Version pinning.
* Offline-cache behaviour.
* Windows-compatible commands.
* Machine-readable search output.
* Agent delegation rules.

---

# 9. SKILL 2 — SUPERPOWERS CODEX

Create:

```text
skills/superpowers-codex/
```

Preserve the complete software-development methodology.

Internal modules must cover at least:

```text
brainstorming
writing-plans
executing-plans
subagent-driven-development
dispatching-parallel-agents
test-driven-development
systematic-debugging
verification-before-completion
requesting-code-review
receiving-code-review
using-git-worktrees
finishing-a-development-branch
writing-skills
```

Do not compress these into generic advice.

Create a parent router that determines which process module applies.

Required routing examples:

```text
new product or feature
→ brainstorming
→ writing-plans
→ implementation

bug or failure
→ systematic-debugging
→ test-driven-development
→ verification

approved implementation plan
→ subagent-driven-development or executing-plans

completed implementation
→ requesting-code-review
→ verification-before-completion
→ finishing-a-development-branch
```

Codex adaptation requirements:

* Use Codex-native agent invocation.
* Use Codex task-list functionality.
* Use `.codex/agents/`.
* Use `.agents/skills/`.
* Detect detached HEAD and managed Codex worktrees.
* Avoid Claude-only command names.
* Map unsupported hooks explicitly.
* Support Windows, WSL, Linux, and macOS.
* Require evidence before completion claims.
* Use bounded delegation rather than agent proliferation.
* Keep implementer agents available through review and repair cycles where the current Codex runtime supports resumed agents.
* Close inactive reviewer agents.
* Fall back to sequential execution if multi-agent runtime support is unavailable.
* Still create all reusable agent definitions even when runtime multi-agent dispatch is unavailable.

---

# 10. SKILL 3 — CODEX MEMORY

Create:

```text
skills/codex-memory/
```

Do not rebuild the memory system from nothing before inspecting the upstream Codex implementation.

First locate and inspect:

* Codex installer code.
* Codex plugin manifest.
* Codex hooks.
* MCP server declaration.
* Memory-search skill.
* Worker service.
* Database schema.
* transcript watchers.
* context-injection logic.
* privacy controls.
* Windows command handling.
* tests covering Codex.

Build an improved Codex-facing layer that preserves the proven upstream storage and retrieval pipeline.

Required workflow:

```text
compact search index
→ filter candidates
→ inspect timeline
→ batch-fetch selected details
→ synthesise only relevant context
```

Required capabilities:

* Persistent cross-session project memory.
* Project isolation.
* Session summaries.
* Observation storage.
* Decision storage.
* File-change awareness.
* Search by project, type, date, and concept.
* Timeline retrieval.
* Batch observation retrieval.
* Token-cost visibility.
* Progressive disclosure.
* Context injection limits.
* Privacy exclusions.
* Secret redaction.
* Data retention controls.
* Health check.
* Backup.
* Export.
* Import.
* Database migration.
* Corruption recovery.
* Windows-safe installation.
* Codex plugin installation.
* MCP server validation.
* uninstall and rollback.
* graceful operation when vector search is unavailable.

Do not inject the entire memory database into context.

Do not duplicate project memory inside `AGENTS.md`.

Do not store credentials, tokens, passwords, private keys, authentication cookies, or MFA values.

Use private-content exclusion markers and automatic secret detection.

Create:

```text
scripts/install-memory.*
scripts/uninstall-memory.*
scripts/doctor-memory.*
scripts/backup-memory.*
scripts/export-memory.*
```

Provide PowerShell and cross-platform implementations where necessary.

---

# 11. SKILL 4 — CODEX DESIGN INTELLIGENCE

Create one top-level skill:

```text
skills/codex-design-intelligence/
```

This skill must combine two intact design engines:

```text
Impeccable
Taste Skill
```

Do not average them together.

Do not dissolve either source into generic design advice.

Use the following responsibility split.

## Impeccable responsibility

Impeccable governs:

* Product context.
* Surface mode.
* UX structure.
* Information architecture.
* Accessibility.
* Responsive design.
* Design-system consistency.
* Production hardening.
* UI critique.
* UI audit.
* UI polish.
* Error states.
* Internationalisation.
* Performance.
* Design documentation.
* Extraction of durable tokens and components.

## Taste Skill responsibility

Taste governs:

* Anti-generic visual judgment.
* Layout character.
* Typography expression.
* Motion intensity.
* Visual density.
* Design variance.
* Strong composition.
* Premium presentation.
* Image-first direction.
* Frontend redesign character.
* Stylistic specialisation.
* Full-output discipline.
* Prevention of repetitive AI-generated layouts.

## Combined routing

```text
brief and product intent
→ Impeccable context and mode

structural UX
→ Impeccable

visual language and anti-generic composition
→ Taste

implementation quality
→ both

technical audit
→ Impeccable

visual-slop audit
→ Taste

final bounded review
→ both, with one consolidated defect report
```

Required design modes:

```text
Persuade
Operate
Read
Experience
```

Required adjustable design dials:

```text
DESIGN_VARIANCE
MOTION_INTENSITY
VISUAL_DENSITY
```

Add a conflict-resolution file:

```text
references/design-authority-matrix.md
```

It must specify which engine wins when rules conflict.

Priority:

```text
explicit user brief
→ product truth
→ accessibility and usability
→ platform conventions
→ established design system
→ selected design mode
→ visual-expression rules
```

Required commands or routing intents must include:

```text
init
shape
design
redesign
critique
audit
polish
bolder
quieter
distill
harden
onboard
animate
colorize
typeset
layout
delight
adapt
optimize
image-to-code
brand-kit
```

Use current source modules instead of inventing incomplete replacements.

---

# 12. SKILL 5 — CODEX SKILL GOVERNOR

Create:

```text
skills/codex-skill-governor/
```

This is the governance layer.

It observes the other four skills but does not replace them.

Required responsibilities:

* Detect reusable workflow discoveries.
* Record meaningful user corrections.
* Detect weak skill triggers.
* Detect missing skill coverage.
* Detect contradictory skills.
* Detect unused complexity.
* Detect repeated agent failures.
* Detect unsafe MCP expansion.
* Record cross-cutting principles.
* Stage skill improvements.
* Run periodic or explicit reviews.
* Maintain attribution.
* prevent live-skill corruption.
* prevent concurrent observation-log corruption.

Stable state must be outside ephemeral worktrees.

Default:

```text
${CODEX_HOME}/state/skillshelf-governor/
```

Windows:

```text
%USERPROFILE%\.codex\state\skillshelf-governor
```

State layout:

```text
observations/
principles/
reviews/
staged-updates/
backups/
evidence/
locks/
config/
```

Mutation sequence:

```text
acquire lock
→ fresh read
→ backup
→ bounded mutation
→ atomic write
→ structural verification
→ survival verification
→ release lock
```

Never modify live skills automatically.

Improvement flow:

```text
read current installed skill
→ copy complete skill package
→ modify staged package
→ compare
→ test
→ produce review report
→ install only with explicit authority
```

Separate these data classes:

```text
project memory
skill-governance observations
```

Do not mix ordinary project history into governance observations.

Do not log one-off preferences as universal methodology.

---

# 13. PRESERVATION ARCHITECTURE

Use both transparent upstream references and self-contained packaged snapshots.

## Upstream submodules

Create:

```text
upstream/
├── vercel-skills/
├── superpowers/
├── claude-mem/
├── impeccable/
├── taste-skill/
└── one-skill-to-rule-them-all/
```

Pin each submodule to the exact commit used for the release.

## Vendored source snapshots

Create:

```text
vendor/
├── find-skills/
├── superpowers/
├── memory/
├── impeccable/
├── taste-skill/
└── skill-governor/
```

Vendor only the source files required to build and understand the adapted implementation.

Do not vendor giant caches, generated dependencies, binaries, build outputs, screenshots unrelated to implementation, databases, package-manager stores, or repository history.

Each vendored source requires:

```text
UPSTREAM.md
PROVENANCE.yml
FILE_MANIFEST.json
SHA256SUMS
LICENSE or licence reference
NOTICE where applicable
```

## Provenance schema

Every adapted skill requires:

```yaml
name:
upstream_repository:
upstream_commit:
upstream_paths:
upstream_authors:
upstream_license:
retrieved_at:
adaptation_target: OpenAI Codex
modified_files:
preserved_behaviours:
extended_behaviours:
removed_behaviours:
removal_reason:
verification_status:
```

Any removed behaviour must have a written technical reason.

“Claude-specific” alone is not sufficient. State the Codex replacement or explain why no equivalent exists.

---

# 14. LICENSING AND ATTRIBUTION

Before copying any source:

1. Locate the exact licence at the pinned commit.
2. Read it.
3. Record redistribution obligations.
4. Retain copyright notices.
5. Retain required attribution.
6. Retain required `NOTICE` content.
7. Mark modified files where the licence requires it.
8. Record source paths and commits.
9. Block publication when licence terms are absent or ambiguous.

Create:

```text
LICENSE
NOTICE
THIRD_PARTY_NOTICES.md
licenses/
├── project/
└── upstream/
```

Do not place all code under one blanket licence when upstream terms differ.

Use a repository-level licence for original SkillShelf code, while preserving source-specific licensing for derivative and vendored content.

Generate an attribution table containing:

```text
Component
Original author
Repository
Pinned commit
Licence
Adaptation
Included paths
```

Do not claim that Sha-Lai Berends authored the original upstream methodologies.

Do claim authorship only for:

* Codex-specific integration.
* SkillShelf orchestration.
* Skill routing.
* Extended tests.
* Additional scripts.
* documentation.
* website.
* provenance system.
* source synchronisation.
* compatibility layer.
* original agents.
* original validation architecture.

---

# 15. SEMANTIC PRESERVATION CONTRACTS

Create a `SEMANTIC_CONTRACT.yml` for every top-level skill.

Each contract must define:

```yaml
mandatory_triggers:
mandatory_workflows:
mandatory_safety_rules:
mandatory_outputs:
mandatory_references:
mandatory_scripts:
prohibited_regressions:
acceptance_scenarios:
```

Create behavioural parity tests.

A test must fail when an adapted skill:

* Stops triggering on a known use case.
* Skips a mandatory process.
* Removes a required verification step.
* bypasses licence validation.
* loads excessive context.
* modifies live governance files unsafely.
* reduces the design skill to generic aesthetics.
* bypasses test-driven development.
* fetches full memory records before filtering.
* installs unverified skills.
* invokes unapproved MCP tools.
* claims success without evidence.

Do not rely only on text-diff tests.

Use scenario-driven behavioural tests.

---

# 16. REPOSITORY STRUCTURE

Build a structure equivalent to:

```text
skillshelf/
├── .agents/
│   └── skills/
│       ├── find-skills-codex/
│       ├── superpowers-codex/
│       ├── codex-memory/
│       ├── codex-design-intelligence/
│       └── codex-skill-governor/
├── .codex/
│   ├── agents/
│   ├── config.example.toml
│   ├── hooks.example.json
│   └── README.md
├── .github/
│   ├── ISSUE_TEMPLATE/
│   ├── PULL_REQUEST_TEMPLATE.md
│   ├── dependabot.yml
│   └── workflows/
├── .agents/
│   └── plugins/
│       └── marketplace.json
├── plugin/
│   ├── .codex-plugin/
│   │   └── plugin.json
│   ├── skills/
│   ├── agents/
│   ├── hooks/
│   ├── scripts/
│   ├── references/
│   └── README.md
├── skills/
│   ├── find-skills-codex/
│   ├── superpowers-codex/
│   ├── codex-memory/
│   ├── codex-design-intelligence/
│   └── codex-skill-governor/
├── agents/
├── mcp/
│   ├── README.md
│   ├── registry.yml
│   ├── policy.yml
│   └── examples/
├── upstream/
├── vendor/
├── licenses/
├── docs/
│   ├── architecture/
│   ├── migration/
│   ├── provenance/
│   ├── skills/
│   ├── agents/
│   ├── mcp/
│   ├── testing/
│   └── handoff/
├── site/
│   ├── src/
│   ├── public/
│   ├── socials/
│   └── tests/
├── scripts/
├── tests/
│   ├── unit/
│   ├── integration/
│   ├── behavioural/
│   ├── provenance/
│   ├── licences/
│   ├── security/
│   └── smoke/
├── AGENTS.md
├── README.md
├── ARCHITECTURE.md
├── MASTER_BUILD_PROMPT.md
├── HANDOFF.md
├── CONTRIBUTING.md
├── SECURITY.md
├── CHANGELOG.md
├── ROADMAP.md
├── THIRD_PARTY_NOTICES.md
├── upstream-lock.json
├── package.json
├── pyproject.toml
└── LICENSE
```

Modify paths only when the current Codex plugin schema requires a different structure.

Document every deviation.

---

# 17. ROOT AGENTS.MD

Create a root `AGENTS.md`.

It must tell Codex to:

1. Read the nearest applicable `AGENTS.md`.
2. Read the selected skill’s current `SKILL.md`.
3. Never use remembered skill content.
4. Check whether prior memory is relevant.
5. Check whether an existing skill should be discovered.
6. Select process skills before implementation skills.
7. Use bounded agents for separable work.
8. Require agents to invoke their own required skills.
9. Apply MCP allowlists.
10. Verify before declaring success.
11. preserve licences and provenance.
12. write meaningful governance observations.
13. avoid loading all references up front.
14. keep context economical through progressive disclosure.
15. never edit vendored source as if it were original source.
16. never silently modify upstream submodules.
17. never automatically merge upstream changes.
18. never publish secrets.
19. never weaken tests to obtain a passing build.
20. update `HANDOFF.md` before final completion.

Routing order:

```text
AGENTS.md
→ skill governor
→ memory relevance check
→ find-skills when capability may exist
→ Superpowers process
→ implementation skill
→ bounded agents
→ verification
→ governance flush
```

---

# 18. CODEX-BUILT AGENTS

Codex must build the agents. The user must not manually create them.

Use the current official Codex custom-agent format.

Create at least:

## `source-inventory-agent`

Responsibilities:

* Inspect upstream trees.
* Find skill files, scripts, references, hooks, manifests, tests, and licences.
* Produce source inventories.
* Identify Codex-native support already present.
* Never modify source.

Required skills:

```text
find-skills-codex
codex-skill-governor
```

MCP allowlist:

```text
GitHub read
filesystem read
OpenAI documentation read
```

## `licence-provenance-agent`

Responsibilities:

* Inspect exact licences.
* Generate attribution.
* detect incompatible or missing licensing.
* Produce provenance manifests.
* Block unsafe redistribution.

Required skill:

```text
codex-skill-governor
```

MCP allowlist:

```text
GitHub read
filesystem read
web read
```

No write access outside provenance staging.

## `codex-port-architect-agent`

Responsibilities:

* Map Claude-specific surfaces to Codex.
* Use official Codex migration guidance.
* Preserve behaviours.
* Produce migration maps.
* Identify unsupported semantics.

Required skills:

```text
find-skills-codex
superpowers-codex
codex-skill-governor
```

## `skill-author-agent`

Responsibilities:

* Build complete adapted skill packages.
* Include references, scripts, tests, provenance, and contracts.
* Never produce bare incomplete `SKILL.md` packages.

Required skills:

```text
superpowers-codex
codex-skill-governor
```

## `memory-integration-agent`

Responsibilities:

* Inspect the upstream Codex memory implementation.
* Improve installation, health checks, privacy, and retrieval.
* Verify MCP operation.
* Maintain progressive disclosure.

Required skills:

```text
codex-memory
superpowers-codex
```

## `design-integration-agent`

Responsibilities:

* Preserve Impeccable and Taste separately.
* Create the authority matrix.
* Build the combined router.
* Design the SkillShelf website.

Required skills:

```text
codex-design-intelligence
superpowers-codex
```

## `mcp-security-agent`

Responsibilities:

* Build the MCP registry.
* Classify read and write tools.
* Validate authentication boundaries.
* Ensure secrets are environment-based.
* Reject broad unneeded permissions.

Required skills:

```text
codex-skill-governor
superpowers-codex
```

## `behavioural-eval-agent`

Responsibilities:

* Build scenario tests.
* Detect semantic regression.
* Compare adapted behaviour with source contracts.
* Produce severity-ranked findings.

Required skills:

```text
superpowers-codex
codex-skill-governor
```

## `code-review-agent`

Responsibilities:

* Review against the implementation plan.
* Review specifications before style.
* Report issues by severity.
* Block critical defects.

Required skill:

```text
superpowers-codex
```

## `release-agent`

Responsibilities:

* Run final checks.
* Verify clean Git status.
* Verify documentation.
* verify GitHub workflows.
* create release notes.
* push the repository.
* verify GitHub Pages deployment.

Required skills:

```text
superpowers-codex
codex-skill-governor
```

---

# 19. AGENT DELEGATION POLICY

Agents preserve the parent context but can increase total token use.

Spawn an agent only when the task is:

* separable;
* bounded;
* evidence-heavy;
* independently verifiable;
* large enough to justify isolated context.

Do not spawn agents for tiny file edits.

Parallelise only independent work.

Examples of safe parallel work:

```text
source inventory
licence inventory
social-page extraction
Codex schema inspection
test-plan creation
```

Do not parallelise conflicting writes to:

```text
AGENTS.md
plugin manifest
upstream-lock.json
package manifests
observation logs
release branch
```

Use one writer per shared file.

Require every agent response to include:

```text
task completed
files inspected
files changed
tests run
evidence
unresolved risks
```

---

# 20. MCP ARCHITECTURE

Create:

```text
mcp/registry.yml
mcp/policy.yml
```

Each MCP entry must define:

```yaml
name:
purpose:
required_by:
transport:
authentication:
read_tools:
write_tools:
confirmation_required:
data_scope:
secret_environment_variables:
installation_status:
validation_command:
fallback:
```

Initial MCP categories:

* GitHub.
* OpenAI developer documentation.
* Persistent memory.
* Filesystem.
* Browser or Playwright for site verification.
* Optional skill registry search.

Rules:

1. No credentials in source files.
2. No example values resembling live secrets.
3. Use environment-variable placeholders.
4. Read access and write access must be separated.
5. Agents receive least-privilege allowlists.
6. Repository writes require authenticated user authority.
7. External write actions require confirmation unless already explicitly authorised by this prompt.
8. MCP failure must have a documented fallback.
9. An unavailable MCP must not cause invented results.
10. All configured MCP servers require a doctor or smoke test.

Create:

```text
mcp/examples/config.toml.example
mcp/examples/environment.example
```

Do not alter the user’s global MCP configuration silently.

---

# 21. PERSONAL SOCIALS PAGE

Reuse the existing socials page from:

```text
berendsshalai/berendsshalai-project-systemtoportfolio
```

Do not recreate the links from memory.

Treat the existing `src/data/socials.ts` as the factual source.

Preserve the existing social destinations unless the source repository contains an updated value.

Required destinations currently represented by the source architecture include:

* GitHub.
* LinkedIn.
* X.
* Facebook.
* Instagram.
* EasyEquities.
* Portfolio website.

Inspect the actual current files before implementation.

Create a SkillShelf site with:

```text
/
├── landing page
├── skills catalogue
├── architecture
├── installation
├── provenance
├── agents
├── MCP registry
├── source credits
└── socials
```

The socials route must be:

```text
/socials/
```

Update page-specific canonical and Open Graph URLs to the SkillShelf GitHub Pages domain.

Do not change the factual social links merely to make them look cleaner.

Preserve:

* accessible labels;
* keyboard navigation;
* semantic HTML;
* responsive behaviour;
* reduced-motion support;
* high contrast;
* metadata;
* structured data;
* `lang="en-ZA"`.

Use `codex-design-intelligence` to redesign the broader SkillShelf site, but preserve the recognisable identity and functional purpose of the existing socials page.

Do not produce a generic gradient-card landing page.

The visual system must communicate:

```text
curated technical archive
precision tooling
open-source lineage
Codex-native engineering
personal authorship without false upstream ownership
```

---

# 22. README REQUIREMENTS

Create a comprehensive root `README.md`.

Required sections:

1. SkillShelf title and positioning.
2. What the repository is.
3. Why it exists.
4. Codex-first statement.
5. Five-skill architecture.
6. Installation.
7. Plugin installation.
8. Local skill installation.
9. Agent system.
10. MCP system.
11. Memory architecture.
12. Design architecture.
13. Governance architecture.
14. Source preservation.
15. Upstream sources.
16. Licence and attribution.
17. GitHub Pages documentation.
18. Social links.
19. Testing.
20. Security.
21. Updating from upstream.
22. Contributing.
23. Roadmap.

Do not claim official affiliation with OpenAI, Anthropic, Vercel, or the upstream authors.

State clearly that SkillShelf is a downstream Codex-oriented integration and adaptation.

---

# 23. INSTALLATION EXPERIENCE

Create a safe installation workflow.

Support:

```text
Codex plugin installation
local project skill installation
global user skill installation
development checkout
uninstall
update
doctor
```

Provide PowerShell commands first, followed by cross-platform commands.

Create scripts such as:

```text
scripts/install.ps1
scripts/install.sh
scripts/uninstall.ps1
scripts/uninstall.sh
scripts/doctor.ps1
scripts/doctor.sh
scripts/update-upstreams.py
scripts/validate-package.py
scripts/build-plugin.py
```

Installation must:

1. Detect Codex.
2. Detect supported plugin features.
3. Validate repository structure.
4. Back up affected configuration.
5. preserve unrelated Codex settings.
6. install only SkillShelf-owned files.
7. validate the installed target.
8. report exactly what changed.
9. provide rollback instructions.

Never delete unrelated skills, agents, hooks, plugins, or MCP servers.

---

# 24. UPSTREAM SYNCHRONISATION

Create:

```text
upstream-lock.json
```

Each source entry must include:

```json
{
  "repository": "",
  "commit": "",
  "branch": "",
  "retrieved_at": "",
  "license": "",
  "source_paths": [],
  "vendor_paths": [],
  "adapted_skill": "",
  "status": ""
}
```

Create an update script that:

1. Fetches upstream refs.
2. Reports new commits.
3. Generates diffs.
4. identifies changed source files.
5. runs licence checks.
6. updates a staging branch.
7. runs semantic-preservation tests.
8. writes a migration report.
9. never automatically merges changes.

Create a scheduled GitHub Action for upstream drift detection.

The action may open an issue or draft pull request.

It must not auto-merge.

---

# 25. TESTING

Build a real test suite.

## Structural tests

Verify:

* exactly five top-level skills;
* valid frontmatter;
* unique skill names;
* referenced files exist;
* scripts exist;
* agent definitions parse;
* plugin manifests parse;
* MCP examples parse;
* no broken internal links;
* no absolute developer-specific paths.

## Provenance tests

Verify:

* each adapted skill has provenance;
* each vendored file has a manifest entry;
* pinned commits exist;
* licence files exist;
* required notices are present;
* modified-file declarations are present where needed;
* SHA-256 hashes match.

## Behavioural tests

Test representative prompts.

### Find Skills

```text
Find a maintained Codex skill for Playwright accessibility testing.
```

Expected:

* search;
* verification;
* compatibility analysis;
* no blind installation.

### Superpowers

```text
Build a new payroll dashboard.
```

Expected:

* brainstorming before implementation;
* plan;
* tests;
* verification.

### Memory

```text
How did this project previously handle authentication?
```

Expected:

* compact search;
* filtering;
* timeline or selected detail fetch;
* no full-database injection.

### Design Intelligence

```text
Redesign this admin dashboard without changing its functionality.
```

Expected:

* product and surface analysis;
* Operate mode;
* structural UX;
* visual-language selection;
* bounded visual QA.

### Skill Governor

```text
The design agent repeatedly ignores mobile overflow.
```

Expected:

* evidence classification;
* relevant observation;
* proposed staged improvement;
* no direct live-skill overwrite.

## Agent tests

Verify:

* required skills are declared;
* MCP allowlists are enforced;
* an agent cannot call an undeclared write tool;
* independent tasks can run in parallel;
* shared-file writes are serialised;
* agents report evidence.

## Security tests

Verify absence of:

* tokens;
* passwords;
* private keys;
* cookies;
* local user secrets;
* database files;
* personal browser sessions;
* `.env` files;
* authentication artefacts.

## Site tests

Verify:

* site builds;
* routes render;
* `/socials/` works;
* external links have safe attributes;
* metadata is correct;
* structured data is valid;
* keyboard navigation works;
* mobile layouts do not overflow;
* reduced-motion behaviour works;
* accessibility scan passes.

## Installation tests

Verify:

* install;
* idempotent reinstall;
* upgrade;
* doctor;
* uninstall;
* rollback;
* preservation of unrelated Codex configuration.

---

# 26. GITHUB ACTIONS

Create workflows for:

```text
continuous integration
skill schema validation
behavioural tests
licence and provenance validation
secret scanning
dependency review
site build
GitHub Pages deployment
upstream drift detection
release packaging
```

Pin action versions.

Use least-privilege workflow permissions.

Do not grant write permissions to workflows that only require read access.

Do not expose secrets to pull requests from forks.

---

# 27. SECURITY

Create `SECURITY.md`.

Include:

* supported versions;
* vulnerability reporting;
* MCP threat model;
* prompt-injection considerations;
* upstream supply-chain risks;
* secret handling;
* memory privacy;
* agent permissions;
* safe update process;
* dependency pinning;
* release verification.

Treat all upstream content as untrusted until inspected.

Search skill files and scripts for:

* hidden install commands;
* remote execution;
* telemetry;
* destructive file operations;
* broad filesystem access;
* secret collection;
* automatic network transmission;
* unsafe shell interpolation.

Document legitimate telemetry and provide opt-out guidance where upstream behaviour supports it.

---

# 28. IMPLEMENTATION PHASES

## Phase 0 — Environment verification

Run:

```text
Git
GitHub CLI
Node.js
npm
Python
Codex CLI
PowerShell
```

Record versions.

Run:

```text
gh auth status
codex --version
git --version
node --version
npm --version
python --version
```

Do not print authentication tokens.

## Phase 1 — Repository resolution

Check whether `berendsshalai/skillshelf` exists.

If absent:

* create the local repository;
* build before publishing;
* create the public GitHub repository;
* push only after tests pass.

If present:

* clone or update;
* inventory;
* back up;
* create a branch such as:

```text
codex/skillshelf-foundation
```

Do not force push.

## Phase 2 — Source acquisition

For each upstream:

* clone or add submodule;
* pin commit;
* inspect tree;
* inspect licence;
* locate Codex-specific code;
* locate Claude-specific code;
* create source inventory.

## Phase 3 — Migration maps

Create one document per source:

```text
docs/migration/<source>-to-codex.md
```

Each map must contain:

```text
source behaviour
source file
Claude mechanism
Codex equivalent
adaptation
preservation test
known limitation
```

## Phase 4 — Skill implementation

Build each complete top-level skill.

Do not proceed to site work while skill packages are structurally incomplete.

## Phase 5 — Agent implementation

Create and validate reusable Codex agents.

## Phase 6 — MCP implementation

Create registry, policy, examples, and tests.

## Phase 7 — Plugin packaging

Inspect the current Codex plugin specification.

Build the plugin using validated schema.

Do not invent fields.

## Phase 8 — Website and socials

Extract the existing personal socials implementation.

Build the SkillShelf documentation site.

## Phase 9 — Testing

Run all tests.

Repair failures.

Do not weaken tests merely to pass.

## Phase 10 — Documentation

Complete:

```text
README.md
ARCHITECTURE.md
MASTER_BUILD_PROMPT.md
HANDOFF.md
CONTRIBUTING.md
SECURITY.md
CHANGELOG.md
ROADMAP.md
THIRD_PARTY_NOTICES.md
```

Store this exact master prompt in:

```text
MASTER_BUILD_PROMPT.md
```

## Phase 11 — Release

* run final validation;
* verify clean Git status;
* create release commit;
* create repository if needed;
* push;
* configure GitHub Pages;
* verify deployment;
* create initial version tag;
* generate release notes.

---

# 29. REQUIRED DOCUMENTATION ARTIFACTS

## `ARCHITECTURE.md`

Document:

* five-skill routing;
* plugin architecture;
* agent architecture;
* MCP architecture;
* memory data flow;
* governance state;
* design authority matrix;
* source preservation;
* sync process;
* security boundaries.

## `HANDOFF.md`

Must contain:

* project state;
* repository URL;
* local path;
* branch;
* last commit;
* tag;
* completed components;
* test results;
* installation commands;
* update commands;
* known limitations;
* unresolved risks;
* upstream pins;
* licences;
* GitHub Pages URL;
* next recommended work;
* exact recovery instructions.

## `CHANGELOG.md`

Use a recognised changelog format.

Initial release:

```text
0.1.0
```

## `ROADMAP.md`

Separate:

```text
required next work
optional improvements
experimental ideas
```

Do not place unfinished mandatory work under “future enhancement.”

---

# 30. COMPLETION GATES

Do not declare completion unless all gates pass.

## Source gate

* All six upstream source repositories inspected.
* Personal socials source inspected.
* Official Codex authority inspected.
* Commits pinned.
* Licences classified.

## Preservation gate

* Every top-level skill has a semantic contract.
* Every adapted skill has provenance.
* Required upstream behaviours have tests.
* No source has been reduced to shallow instructions.

## Codex gate

* Skills are discoverable by Codex.
* Agents are valid.
* Plugin validates.
* MCP examples validate.
* hooks are current and supported.
* migration validator passes where applicable.

## Memory gate

* Worker health check passes.
* Database can initialise.
* Search workflow works.
* retrieval remains progressive.
* privacy exclusions work.
* uninstall works.

## Design gate

* Impeccable and Taste remain separately identifiable.
* Authority matrix exists.
* Site passes desktop and mobile review.
* Social links match the existing factual source.
* Accessibility tests pass.

## Governance gate

* Stable state path works.
* locks work.
* atomic writes work.
* concurrent observation test passes.
* staged updates do not touch live skills.

## Repository gate

* GitHub repository exists.
* default branch exists.
* source is pushed.
* GitHub Actions are present.
* GitHub Pages is configured.
* README renders.
* no secret is committed.
* Git status is clean.

---

# 31. FAILURE POLICY

When a capability is unavailable:

1. Record the exact failure.
2. Use a safe fallback.
3. Continue all work that remains possible.
4. Do not invent success.
5. Mark the affected acceptance gate accurately.
6. Write exact remediation in `HANDOFF.md`.

Examples:

* GitHub authentication unavailable:

  * complete local repository;
  * create all commits;
  * provide exact authenticated push commands;
  * do not claim the remote repository was created.

* Codex multi-agent unavailable:

  * create all agent definitions;
  * execute the implementation sequentially;
  * record the runtime limitation.

* MCP unavailable:

  * use direct CLI or local API where authorised;
  * retain validated example configuration;
  * record the missing live validation.

* Upstream licence unclear:

  * do not copy the affected content;
  * retain a source reference and migration design;
  * mark publication blocked for that component.

* GitHub Pages deployment unavailable:

  * complete and test the site locally;
  * commit the workflow;
  * provide the exact deployment state.

Partial honesty is mandatory. False completion is prohibited.

---

# 32. FINAL RESPONSE FORMAT

Your final Codex response must contain:

## Repository

```text
Local path:
GitHub repository:
Branch:
Commit:
Tag:
GitHub Pages:
```

## Build result

A concise table:

```text
Component | Status | Evidence
```

Include:

* Find Skills.
* Superpowers.
* Memory.
* Design Intelligence.
* Skill Governor.
* Agents.
* MCP.
* Website.
* Socials.
* Tests.
* Documentation.
* Release.

## Source preservation

```text
Source | Pinned commit | Licence | Adaptation status
```

## Tests

```text
Suite | Passed | Failed | Skipped
```

## Limitations

Only real unresolved limitations.

## Installation

Provide the tested Codex installation command.

## Handoff

Point to:

```text
HANDOFF.md
```

Do not end with vague statements such as:

```text
The project should now work.
Most features are implemented.
You can finish the remaining pieces later.
```

Use evidence.

---

# 33. START NOW

Begin with:

```text
1. Environment verification.
2. Repository existence check.
3. Source and licence inventory.
4. Official Codex schema inspection.
5. Build plan.
6. Agent delegation.
7. Implementation.
8. Validation.
9. Publication.
```

Do not ask the user to create the agents.

Do not ask the user to manually copy the upstream skills.

Do not ask the user to decide routine implementation details already resolved by this prompt.

Do not stop after planning.

Build the complete SkillShelf repository.
