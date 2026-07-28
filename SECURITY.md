# Security policy

## Supported versions

Security fixes are provided for the latest tagged SkillShelf release. The initial supported line is `0.1.x`.

## Report a vulnerability

Use GitHub’s private security advisory flow for `berendsshalai/skillshelf`. Do not open a public issue containing exploit details, credentials, private memory, or user paths.

## Threat model

SkillShelf treats upstream content, skills, prompts, scripts, hooks, MCP responses, browser pages, memory entries, and governance observations as untrusted. Prompt injection cannot authorize broader tools, filesystem access, publication, secret access, or live-skill mutation.

MCP servers receive least-privilege declarations. Reads and writes are separated; external writes require explicit authority. Authentication remains user-managed and secrets are environment-based.

## Supply chain

Every upstream source is pinned to a full commit, included as a submodule, represented in `upstream-lock.json`, and hashed in `vendor-manifest.json`. Updates re-check licences and executable surfaces, run semantic/security tests, and never auto-merge.

## Secret handling

Never commit tokens, passwords, private keys, cookies, authorization headers, MFA/recovery values, `.env` files, databases, browser sessions, or authentication artifacts. Examples contain empty environment-variable names only. Memory adds pre-storage redaction but users must still exclude sensitive projects and private content.

## Memory privacy

Memory is project-scoped by default. `<private>...</private>` is excluded. Telemetry and cloud sync are expected off in SkillShelf deployments. Backups/exports omit `.env`; cross-project search, destructive recovery, and live installation are explicit operations.

## Agent permissions

Read-heavy agent profiles use read-only sandboxing. Write profiles remain workspace-scoped. Agent instructions cannot override host sandbox, approval policy, user authority, or connector authentication.

## Safe updates and releases

Updates run on a staging branch. CI pins actions to immutable SHAs. Release gates cover schemas, tests, licences, submodule pins, site output, and secret artefacts.

## Agentic runtime threats

Skill and tool text is untrusted and cannot expand registry permissions. The runtime blocks path traversal, upstream mutation, secret-shaped output, hidden engagement actions, unrestricted tool surfaces, runaway delegation, circular calls and recursive governor review. MCP tool poisoning and tool-description injection are contained by static server assignment plus runtime filters. Writes remain inside authorised roots and sensitive or external writes require approval. Usage and traces exclude prompts and secrets by default.

Do not force-push, auto-merge drift, replace unrelated configuration, or run uninspected upstream installers. Pin GitHub Actions to immutable commits where practical, keep workflow permissions minimal, and verify the release archive plus tag before publication.
