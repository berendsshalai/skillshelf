# Privacy and secret handling

## Capture policy

Allow project decisions, summaries, observations, file paths, and non-sensitive tool outcomes. Deny credentials, authentication artifacts, private keys, cookies, MFA/recovery data, database connection strings, `.env` contents, browser/session state, and material inside `<private>...</private>`.

Run `scripts/redact-secrets.*` on external transcripts before import. The detector covers common API tokens, AWS access keys, bearer tokens, credential assignments, private-key blocks, JWTs, and session/auth/cookie assignments. Treat it as defense in depth, not proof that content is safe.

## Upstream distinction

The upstream privacy validator suppresses a turn when its stored user prompt is empty after private-marker stripping. The audited upstream secret scrubber protects telemetry errors, but it is not an ordinary memory-ingestion secret detector. SkillShelf therefore adds a separate pre-storage redactor.

## Telemetry

Set `CLAUDE_MEM_TELEMETRY=0` or `DO_NOT_TRACK=1` for the privacy-first default. Upstream analytics otherwise default on and may backfill anonymized historical daily activity. Error telemetry is separately scrubbed and gated, but remains network transmission.

## Retention

Retention is user policy. Before deletion:

1. stop the worker;
2. create and verify an export;
3. identify the exact project/session scope;
4. prefer supported worker/API deletion;
5. verify deletion and vector-index reconciliation.

Do not silently retain deleted SQLite content in exports, vector indexes, sync outboxes, or cloud replicas. Document those limitations when an enabled backend cannot be purged in the same operation.

## Sync

Cloud sync is optional and off by default upstream. Enabling it expands the data boundary to configured hubs and requires separate authentication, retention, deletion, and threat-model review.
