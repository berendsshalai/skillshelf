# Contributing

Open an issue or focused pull request. Keep upstream work attributed and vendored snapshots byte-identical to their recorded commits.

For a source update:

1. Create a staging branch.
2. Update the submodule pin.
3. Inspect the exact licence, notices, scripts, hooks, MCP, telemetry, and destructive operations.
4. Replace the complete required vendor slice.
5. Update `upstream-lock.json`, provenance, migration map, semantic contract, differences, notices, and hashes.
6. Run `npm run check` plus the focused skill tests.
7. Include evidence and known limitations in the pull request.

Do not submit credentials, private memory, generated user state, package caches, provider mirrors, or changes that weaken tests to pass.
