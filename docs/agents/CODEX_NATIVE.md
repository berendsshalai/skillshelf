# Codex-Native Definitions

## Purpose

Codex-native TOML definitions provide the same six normal runtime roles represented by the SDK registry.

## Architecture

Generation produces one master and five specialist TOMLs under `.codex/agents` and `agents/generated/codex`. Eight maintenance TOMLs are generated separately under `agents/generated/maintenance` and remain opt-in.

## Configuration

Edit `agents/registry.yml` or source instruction files, not generated TOMLs. Regenerate after reviewed changes.

## Commands

```powershell
python scripts/generate-agents.py --check
python scripts/generate-agents.py
```

## Examples

The generated `memory-agent.toml` points to the memory instruction and bounded role; it is not a copy of the entire memory store.

## Failure Modes

Manual generated-file edits drift, stale generation mismatches registry policy, and unavailable host tools can limit execution.

## Security Boundaries

Native definitions inherit bounded instructions but actual host permissions remain authoritative. Generated maintenance TOMLs must not be installed as normal runtime specialists implicitly. Host-recorded tool calls and changes are evidence; model claims about execution are interpretation.

## Tests

Generation checks compare source and outputs and `doctor` expects exactly six generated Codex runtime TOMLs. These checks are offline.

## Recovery

Restore source-of-truth files and regenerate. Review diffs before committing generated changes.

## Known Limitations

Parity covers declared roles and policy, not identical behavior across Codex and SDK models/tools. Host credentialled behavior requires separate verification.
