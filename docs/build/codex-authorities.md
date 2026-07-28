# Current Codex authorities

Audited 2026-07-28:

| Authority | Commit | Licence finding | Use |
|---|---|---|---|
| `openai/skills` | `49f948faa9258a0c61caceaf225e179651397431` | Per-skill; no blanket root licence | Deprecated migration reference only |
| `openai/plugins` | `11c74d6ba24d3a6d48f54a194cd00ef3beea18f9` | Per-component; no blanket root licence | Maintained packaging and marketplace examples |
| `openai/codex` | `8e271dc02b23d42827875019924be0f5005642b0` | Apache-2.0 + NOTICE | Runtime manifest, marketplace, agent, MCP, hooks, and Windows behavior |

Decisions:

- Use `.codex-plugin/plugin.json`, `.agents/plugins/marketplace.json`, `.agents/skills/`, and `.codex/agents/*.toml`.
- Marketplace local sources use the canonical `./plugins/skillshelf` package tree.
- Resource paths start with `./` and remain inside the plugin root.
- Skills require `name` and `description`; UI metadata uses `agents/openai.yaml`.
- Hooks are stable/default-on in the audited runtime, but SkillShelf declares no root hook because it does not ship a trusted executable hook.
- The older migrate-to-codex hook matrix is stale: current feature key is `hooks`; legacy `codex_hooks` is deprecated.
- Secrets remain environment references only. MCP executable commands are argv-style, not shell strings.
