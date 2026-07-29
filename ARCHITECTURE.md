# SkillShelf Architecture 0.4.0

## Release and package model

`VERSION` is the canonical release version. `scripts/validate-version.py` verifies matching versions in the Node tooling package, root and packaged plugin manifests, Python wheel metadata, changelog, and site stamp.

The Codex plugin, Python wheel/runtime, and generated agent definitions are distinct:

- The plugin packages five discoverable skills.
- The wheel provides `skillshelf_agents`, the `skillshelf` CLI, runtime services, and integration modules.
- Native Codex TOMLs and the SDK registry snapshot are generated from `agents/registry.yml`.

Installing one artifact does not imply that every other artifact or optional dependency is installed.

## Two agent planes

The normal execution plane contains exactly six definitions: one master and five specialists. The master retains user communication and may call specialists as bounded tools. Specialists do not call the master or themselves.

The maintenance plane contains eight opt-in definitions: behavioural evaluation, code review, Codex migration, design integration, MCP security, memory integration, release, and source audit. These definitions maintain the repository; they are not loaded by `RuntimeRegistry`, not candidates in deterministic routing, and not a flat extension of the user-facing runtime.

## Routing and evidence

Deterministic phrase rules directly select one specialist only at confidence `0.90` or above. Ties and unmatched requests remain with the master. Registry policy supplies model profiles, skills, allowed MCP categories, capabilities, prohibitions, turn limits, and token budgets.

Specialist summaries and findings are model interpretation. Artifact hashes, file changes, test executions, and tool executions are runtime-derived evidence and overwrite model-authored claims before results are trusted.

## Skill loading

Codex discovers five parent skills. The SDK reads metadata before loading a selected skill body, and referenced resources remain directory-bound. Vendored modules do not expand the discoverable root. This preserves methodology while reducing unnecessary context.

## Integration plane

The deterministic local integration stack contains:

```text
validated connector manifest + environment secret reference
  → safe REST read against an allowlisted host
  → immutable raw record + canonical normalization or quarantine
  → Decimal price decision + deterministic delivery quote
  → consent/authority/template-governed mock messages
  → durable SQLite workflow state
  → idempotent asynchronous webhook completion
```

SQLite FTS5 supplies local cited retrieval; deterministic capability rules supply suggestions. A limited FastAPI control plane exposes health, readiness, local connector configuration, state inspection, webhook inboxing, usage counts, and suggestions. Connector sync and workflow execution endpoints deliberately fail closed until typed configured services are wired.

No PostgreSQL, live carrier, live email/WhatsApp, hosted control plane, or generated OpenAPI release artifact is claimed. FastAPI can expose its runtime schema when the optional web dependency is installed, but OpenAPI generation is not a release deliverable.

## MCP and authority

`mcp/registry.yml` declares transports, authentication references, tools, confirmation, data scope, installation state, and fallback. `mcp/policy.yml` denies undeclared tools and separates reads from writes. Secret values are environment-owned and never stored in examples.

Routing does not grant authority. Sensitive writes require the appropriate runtime authority and, where applicable, exact approval. Unavailable services degrade explicitly rather than producing invented results.

## Memory and governance state

Sessions, project memory, integration databases, and governance observations are separate stores. Memory flow is project-filtered and privacy-first:

```text
transcript → private/secret filtering → compact search
→ selected timeline → selected observations → bounded synthesis
```

Governance state defaults below `${CODEX_HOME}/state/skillshelf-governor/`. Mutations use locks, fresh reads, backups, bounded staged changes, atomic replacement, verification, and rollback records. Live skills remain read-only inputs until explicit approval succeeds.

## Source preservation and licensing

Pinned submodules preserve upstream history; vendored snapshots make the package self-contained; SHA-256 manifests bind copied files. `upstream-lock.json`, per-skill provenance, and `THIRD_PARTY_NOTICES.md` preserve source, commit, licence, notice, and attribution requirements. SkillShelf’s root MIT licence does not override MIT, Apache-2.0, or CC BY 4.0 terms attached to vendored files.

## Proof boundary

Offline tests validate structure, routing, policy, integrations, installers, memory administration, governance, and packaging without provider credentials. Credentialled model quality, live MCP workers, live communications/carriers, and external service availability require separate protected validation and must be reported as deferred or skipped until run.
