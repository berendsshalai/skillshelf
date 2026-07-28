from __future__ import annotations

from .contracts import RouteDecision

RULES = {
    "find-skills-agent": ("find a skill", "discover skill", "installable skill", "skill for"),
    "memory-agent": ("what did we", "last week", "previously", "prior decision", "remember"),
    "design-intelligence-agent": ("redesign", "design this", "dashboard", "visual audit", "frontend polish"),
    "skill-governor-agent": ("stage this reusable", "governor", "reusable improvement", "proposal"),
    "superpowers-agent": ("debug", "failing test", "implement", "fix", "code review", "build"),
}


def route_task(task: str, explicit_agent: str | None = None) -> RouteDecision:
    if explicit_agent:
        return RouteDecision(
            direct_agent=explicit_agent,
            candidate_agents=[explicit_agent],
            confidence=1.0,
            reasons=["explicit agent selection"],
            requires_master=False,
        )
    lowered = task.casefold()
    scores = {agent: sum(term in lowered for term in terms) for agent, terms in RULES.items()}
    ranked = sorted((score, agent) for agent, score in scores.items() if score)
    if not ranked:
        return RouteDecision(confidence=0.0, reasons=["no deterministic rule matched"], requires_master=True)
    best, agent = ranked[-1]
    tied = sum(1 for score, _ in ranked if score == best) > 1
    confidence = 0.95 if best >= 1 and not tied else 0.75
    candidates = [name for score, name in reversed(ranked) if score == best]
    return RouteDecision(
        direct_agent=agent if confidence >= 0.90 else None,
        candidate_agents=candidates,
        confidence=confidence,
        reasons=[f"matched {best} routing signal(s)"],
        requires_master=confidence < 0.90,
    )
