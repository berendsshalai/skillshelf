# Superpowers → Codex

| Source behavior | Source file | Claude mechanism | Codex equivalent | Adaptation | Preservation test | Limitation |
|---|---|---|---|---|---|---|
| Bootstrap process discipline | `using-superpowers/SKILL.md` | session-start context injection | Native skill discovery/router | No dominance hook; explicit authority precedence | Exactly one router; full modules remain | No automatic hook bootstrap |
| Delegate approved plans | `subagent-driven-development/` | Task agents | Codex subagents | Bounded delegation with sequential fallback | Agent definitions + routing tests | Runtime concurrency varies |
| Track work | `writing-plans/` | TodoWrite conventions | Codex task plan | Preserve plan/checkpoint semantics | Behavioral scenario | UI varies by surface |
| Worktree isolation | `using-git-worktrees/` | Claude shell workflow | Git plus managed-worktree detection | Detect detached/host-owned worktrees | Contract fixture | Host-managed branch operations may be unavailable |
