# Agent registry

`registry.yml` is the single source of truth for the native Codex definitions and the Python Agents SDK runtime. Run `python scripts/generate-agents.py --check` to detect drift or run it without `--check` to regenerate files.

The master owns user communication. Specialists are bounded tools, load one skill lazily, receive only relevant context, and return a strict output contract.
