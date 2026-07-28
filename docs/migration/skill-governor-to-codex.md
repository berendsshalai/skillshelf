# One Skill to Rule Them All → Codex

| Source behavior | Source file | Source mechanism | Codex equivalent | Adaptation | Preservation test | Limitation |
|---|---|---|---|---|---|---|
| Observe reusable lessons | `SKILL.md` | prose observation log | stable Codex-home state | Typed governance observations only | Schema/secret tests | Human judgment remains required |
| Concurrent safe update | `references/weekly-review.md` | optimistic re-read | O_EXCL locks + atomic replace | Implement real lock/backup/survival sequence | thread/process stress tests | Filesystem atomicity depends on host |
| Stage improvements | `references/skill-authoring.md` | full-copy staging | staged package + hash manifest | No live install command | Live-skill unchanged tests | Installation always external/explicit |
| Stable storage | `references/environments.md` | workspace guidance | `${CODEX_HOME}/state/...` | Worktree-independent layout | state-root tests | Locked-down environments need handoff mode |
