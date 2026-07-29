# SkillShelf Roadmap after 0.4.0

## Current baseline

0.4.0 establishes:

- one `VERSION` source with consistency validation across packaging surfaces;
- five provenance-preserving skills;
- six normal runtime definitions and eight separate opt-in maintenance definitions;
- distinct plugin, Python wheel/runtime, and generated native-agent artifacts;
- deterministic offline routing, policy, governance, packaging, and integration proof;
- local REST/SQLite/Decimal/delivery/mock-communications/workflow/FTS/suggestion components;
- a limited local control-plane API that fails closed for unwired live operations.

These are local and offline capabilities unless a command explicitly uses configured credentials.

## Required next work

- Run protected credentialled quality evaluations against representative private tasks and report them separately from offline fixtures.
- Validate the pinned upstream memory worker and MCP end to end in a disposable Codex profile.
- Implement and verify live connector credential flows, webhook signatures, and provider-specific schemas before enabling sync.
- Add live carrier and communication adapters with sandbox accounts, consent review, delivery reconciliation, and secret-manager integration.
- Define production persistence, migrations, backup/restore, tenant isolation, and concurrency requirements before considering a database beyond local SQLite.
- Wire typed stock-to-offer execution and approvals into the control-plane API only after authentication, tenant authorization, idempotency, body limits, and audit controls exist.

## Release and packaging work

- Keep `VERSION` authoritative and make release automation reject every inconsistent wheel, plugin, Node, changelog, site, or tag version.
- Test wheel installation and plugin installation independently; neither artifact should imply installation of the other.
- Add signed provenance and build attestations without weakening upstream licence and notice preservation.
- Submit the skills-only plugin for external directory review only if desired; a public repository is not marketplace approval.

## Optional improvements

- Add a dedicated Windows CI runner for PowerShell install/reinstall/uninstall isolation.
- Add browser-based accessibility checks for documentation routes.
- Add deterministic cursor and Link-pagination fixtures alongside the current page-number proof.
- Add tenant-aware retrieval authorization and safer full-text query parsing.
- Add operational metrics and trace export with sensitive data disabled by default.

## Experimental ideas

- Optional local vector retrieval behind the same citation and progressive-disclosure contract.
- A read-only provenance explorer for upstream diffs.
- A production database adapter evaluated against explicit requirements; PostgreSQL is not currently implemented or selected.
- A generated OpenAPI release artifact only after the HTTP surface is complete and versioned; runtime FastAPI schema availability is not that deliverable.

## Non-goals until verified

Do not claim live provider readiness, credentialled evaluation success, hosted control-plane availability, PostgreSQL support, generated OpenAPI publication, universal plugin-directory approval, or automatic self-improvement. Maintenance agents remain opt-in, and live skill changes remain approval-gated.

All future upstream work must retain provenance files, licence notices, attribution, semantic-preservation review, and reversible staging.
