# claude-mem → Codex

| Source behavior | Source file | Claude mechanism | Codex equivalent | Adaptation | Preservation test | Limitation |
|---|---|---|---|---|---|---|
| Lifecycle capture | `plugin/hooks/codex-hooks.json` | Claude/Codex hooks | Current Codex hooks with `commandWindows` | Preserve native Codex path; explicit install | Vendored hash and hook schema evidence | Compiled worker is upstream-installed |
| Progressive retrieval | `plugin/skills/mem-search/SKILL.md` | MCP search/timeline/get | Same MCP tools | Enforce project scope and selected batches | Retrieval contract tests | Vector search optional |
| Privacy | privacy validators/private markers | opt-out telemetry, private marker | pre-storage redaction + telemetry off expectation | Add secret detection and safe backup/export | Redaction/admin tests | Pattern detection is not perfect |
| Legacy context | tagged `AGENTS.md` injection | transcript watcher | native hooks | Suppress duplicate AGENTS memory | Semantic contract | Legacy mode remains upstream compatibility |
