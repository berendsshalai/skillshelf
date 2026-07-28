# SkillShelf agent workflow map

## Purpose

The workflow map is the maintained visual contract for SkillShelf's user-facing
agent runtime. It describes both the Codex-native runtime and the OpenAI Agents
SDK manager pattern. The SVGs are canonical README assets; the Mermaid source
is the editable logical model.

## Why the orchestrator is central

`SkillShelfMaster` is the single orchestration brain. It interprets the complete
goal, classifies intent and risk, selects the smallest sufficient specialist
set, controls ordering and context, enforces approvals and budgets, reconciles
runtime evidence, and communicates the final result. Specialists never bypass
the master or communicate a final answer directly to the user.

The six user-runtime definitions are distinct from the opt-in repository
maintenance definitions. The factual names, contracts, permissions, and
budgets come from [`agents/registry.yml`](../../agents/registry.yml).

## User input contract

The orchestrator receives the complete goal, relevant context and files,
constraints, and the user's approval authority. A request does not implicitly
grant write, installation, publication, communication, or external-service
authority.

## Delegation contract

Each selected specialist receives a bounded `DelegationInput`: task, success
criteria, relevant paths, compact context, allowed and prohibited capabilities,
token limits, and trace identifiers. The master does not copy the entire
conversation or load every skill for every task.

```text
bounded input → specialist process → structured result → master reconciliation
```

## Find Skills Agent

The [Find Skills Agent](../../agents/instructions/find-skills-agent.md) loads
[`find-skills-codex`](../../skills/find-skills-codex/README.md).

- Input: capability gap, platform, installed skills, security/licence constraints,
  and requested installation scope.
- Process: search trusted sources, pin candidate versions, inspect instructions
  and referenced files, audit scripts/hooks/MCP/telemetry/licences, score
  compatibility, and reject unsafe candidates.
- Output: ranked candidates, source and version evidence, security findings,
  trade-offs, guidance, and unresolved limitations.

## Superpowers Agent

The [Superpowers Agent](../../agents/instructions/superpowers-agent.md) loads
[`superpowers-codex`](../../skills/superpowers-codex/README.md).

- Input: feature, bug, or review request; repository context; acceptance criteria;
  relevant files; and constraints.
- Process: inspect current behaviour, identify constraints and edge cases, plan,
  apply test-driven changes where useful, modify only authorised files, run
  validation, and review the result.
- Output: working patch, changed-file evidence, test results, review findings,
  risks, and recovery instructions.

## Memory Agent

The [Memory Agent](../../agents/instructions/memory-agent.md) loads
[`codex-memory`](../../skills/codex-memory/README.md).

- Input: project identity, recall question, time/topic filters, relevant session
  context, and privacy scope.
- Process: search the compact index, filter candidates, inspect a bounded
  timeline, fetch selected observations, exclude secrets, distinguish evidence
  from inference, and compress useful context.
- Output: prior decisions, project history, selected observations, timeline
  context, confidence, and source distinctions.

## Design Intelligence Agent

The [Design Intelligence Agent](../../agents/instructions/design-intelligence-agent.md)
loads [`codex-design-intelligence`](../../skills/codex-design-intelligence/README.md).

- Input: interface brief, existing frontend/design system, supplied references,
  accessibility requirements, platform, and viewport.
- Process: inspect product truth, choose the surface mode, apply structural and
  visual guidance, preserve functionality, audit hierarchy/accessibility and
  responsiveness, implement bounded improvements, and perform consolidated QA.
- Output: implementation or recommendations, accessibility and usability
  findings, responsive evidence, visual findings, and remaining risks.

## Skill Governor Agent

The [Skill Governor Agent](../../agents/instructions/skill-governor-agent.md)
loads [`codex-skill-governor`](../../skills/codex-skill-governor/README.md).

- Input: execution observations, repeated failures, user corrections, evaluation
  failures, and candidate reusable improvements.
- Process: separate reusable methodology from project history, validate evidence
  and scope, detect contradictions, stage a complete proposal, run structural
  and behavioural evaluations, record regression risks, and wait for approval.
- Output: governance observations, cross-cutting principles, staged proposals,
  evaluation reports, and an approval-safe upgrade path.

## Structured return contracts

The first four specialists return a `SpecialistResult`; the governor returns a
`GovernanceResult`. Both carry a compact summary and structured findings.
Artifact hashes, tool calls, file changes, and tests are reconciled from runtime
evidence rather than trusted merely because model text claims them.

## Sequential versus parallel specialist use

The master may parallelise independent read-only work. Dependent or mutating
work is sequenced through the master:

```text
Orchestrator → Specialist A → Orchestrator → Specialist B → Orchestrator
```

There is no unrestricted specialist-to-specialist channel. The master retains
the ordering decision and passes only the verified context needed for the next
step.

## Context-economy rules

- Select the smallest sufficient specialist set.
- Load only the chosen specialist's current skill and relevant references.
- Prefer paths, summaries, hashes, and selected observations over full histories.
- Enforce registry turn and token budgets.
- Return truthful partial results when a hard budget is exhausted.

## Approval and tool boundaries

Routing never grants authority. Registry allowlists constrain tools and MCP
categories; prohibited capabilities remain denied. Sensitive calls require
approval bound to the exact operation and arguments. Specialists cannot expand
permissions, approve themselves, or publish merely because they can recommend
an action. See the [MCP registry](../../mcp/registry.yml),
[MCP policy](../../mcp/policy.yml), and
[support actions](SUPPORT_ACTIONS.md).

## Example workflows

### Memory-only request

```text
User → Orchestrator → Memory Agent → Orchestrator → Final response
```

Only the Memory Agent receives the bounded recall question and project scope.

### Software implementation

```text
User → Orchestrator → Superpowers Agent → Orchestrator → Final response
```

The master supplies the repository scope and acceptance criteria, then
reconciles changed files and test evidence.

### Frontend implementation with two specialists

```text
User → Orchestrator → Design Intelligence Agent → Orchestrator
     → Superpowers Agent → Orchestrator → Final response
```

The orchestrator controls the sequence: design findings become bounded input to
the implementation specialist only after they return to the master.

## Related documentation

- [Master contract](MASTER.md)
- [Specialist contracts](SPECIALISTS.md)
- [Routing](ROUTING.md)
- [OpenAI Agents SDK runtime](SDK.md)
- [MCP architecture and authority](../../ARCHITECTURE.md#mcp-and-authority)
- [Evaluations](EVALUATIONS.md)
- [Editable Mermaid source](../diagrams/skillshelf-agent-workflow.mmd)
