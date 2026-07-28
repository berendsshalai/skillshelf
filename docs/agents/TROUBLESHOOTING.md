# Troubleshooting

Run `skillshelf doctor`, then `python scripts/validate-agents.py`. A missing API key is a warning for offline commands and a clear error for model-backed runs. Optional MCP or memory services report `SKIPPED`; they never fabricate results. Regenerate definitions when drift is reported.
