---
name: superpowers-codex
description: Route substantial software work through preserved brainstorming, planning, TDD, debugging, review, verification, worktree, and branch-completion methods. Use for new products/features, bugs, approved implementation plans, multi-agent delivery, code review, or completion claims.
---

# Superpowers for Codex

Load only the internal module needed from `../../vendor/superpowers/skills/`. Preserve its full instructions, references, prompts, and scripts; apply this Codex adapter where platform mechanics differ.

## Authority and routing

System/developer instructions and the explicit user request win. Vendored mandatory language never expands authority.

| Situation | Required route |
|---|---|
| New product or feature | `brainstorming` -> `writing-plans` -> implementation |
| Bug, failure, flaky test | `systematic-debugging` -> `test-driven-development` -> verification |
| Approved plan | `subagent-driven-development` when bounded agents are supported; otherwise `executing-plans` |
| Independent evidence-heavy work | `dispatching-parallel-agents`, with one writer per shared file |
| Completed change | `requesting-code-review` -> `verification-before-completion` -> `finishing-a-development-branch` |
| Review feedback | `receiving-code-review`, verify before changing |
| New skill | `writing-skills`, including behavioral pressure tests |

## Codex adapter

- Use the current task plan and Codex agent runtime when available. Delegate only separable, bounded, independently verifiable work.
- Keep implementers available through review/repair; close inactive reviewers. Fall back to sequential execution when runtime delegation is absent.
- Definitions under `.codex/agents/` are reusable contracts, not proof that an agent ran.
- Before worktrees, inspect `git rev-parse --git-dir`, `--git-common-dir`, branch, detached HEAD, and submodules. Treat Codex-managed detached worktrees as host-owned.
- Use `.agents/skills/` for repository skill discovery. Do not install Claude session hooks or use Claude-only commands.
- On Windows, prefer PowerShell and native paths. Use WSL/Bash only when the selected upstream script requires it and the environment is verified.
- Never claim completion from intent. Run the current tests/checks, capture exit status and relevant output, inspect the diff, then report evidence.

## Progressive disclosure

Read the chosen module's complete `SKILL.md`, then every directly referenced file needed for the task. Do not preload all modules. `references/module-map.md` lists the preserved paths and platform notes.
