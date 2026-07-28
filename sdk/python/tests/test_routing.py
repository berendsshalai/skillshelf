from skillshelf_agents.routing import route_task


def test_required_routes():
    cases = {
        "find a skill for React testing": "find-skills-agent",
        "debug this failing test": "superpowers-agent",
        "what did we decide last week?": "memory-agent",
        "redesign this dashboard": "design-intelligence-agent",
        "record and stage this reusable improvement": "skill-governor-agent",
    }
    for task, expected in cases.items():
        assert route_task(task).direct_agent == expected


def test_ambiguous_uses_master_and_explicit_wins():
    assert route_task("help with a thing").requires_master
    assert route_task("anything", "memory-agent").direct_agent == "memory-agent"
