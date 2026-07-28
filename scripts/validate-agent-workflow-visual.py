#!/usr/bin/env python3
"""Validate the maintained SkillShelf agent-workflow visual."""

from __future__ import annotations

import pathlib
import re
import sys
import xml.etree.ElementTree as ET

ROOT = pathlib.Path(__file__).resolve().parents[1]
LIGHT = ROOT / "docs/assets/skillshelf-agent-workflow.svg"
DARK = ROOT / "docs/assets/skillshelf-agent-workflow-dark.svg"
MERMAID = ROOT / "docs/diagrams/skillshelf-agent-workflow.mmd"
WORKFLOW_DOC = ROOT / "docs/agents/WORKFLOW_MAP.md"
README = ROOT / "README.md"

GROUP_IDS = {
    "user-input",
    "skillshelf-orchestrator",
    "find-skills-agent",
    "superpowers-agent",
    "memory-agent",
    "design-intelligence-agent",
    "skill-governor-agent",
    "final-response",
    "legend",
}
SPECIALISTS = GROUP_IDS - {
    "user-input",
    "skillshelf-orchestrator",
    "final-response",
    "legend",
}
AGENT_NAMES = {
    "SkillShelf Master",
    "Find Skills Agent",
    "Superpowers Agent",
    "Memory Agent",
    "Design Intelligence Agent",
    "Skill Governor Agent",
}
GROUP_NAMES = {
    "find-skills-agent": "Find Skills Agent",
    "superpowers-agent": "Superpowers Agent",
    "memory-agent": "Memory Agent",
    "design-intelligence-agent": "Design Intelligence Agent",
    "skill-governor-agent": "Skill Governor Agent",
}


def fail(message: str) -> None:
    raise AssertionError(message)


def local_name(tag: str) -> str:
    return tag.rsplit("}", 1)[-1]


def parse_svg(path: pathlib.Path) -> tuple[ET.Element, set[str], set[str]]:
    try:
        root = ET.parse(path).getroot()
    except (ET.ParseError, OSError) as exc:
        fail(f"{path.relative_to(ROOT)} is not valid SVG: {exc}")
    id_list = [element.get("id") for element in root.iter() if element.get("id")]
    if len(id_list) != len(set(id_list)):
        fail(f"{path.name}: duplicate SVG IDs")
    ids = set(id_list)
    labels = {
        " ".join("".join(element.itertext()).split())
        for element in root.iter()
        if local_name(element.tag) == "text"
    }
    return root, ids, labels


def validate_svg(path: pathlib.Path) -> set[str]:
    root, ids, labels = parse_svg(path)
    children = list(root)
    if not any(local_name(child.tag) == "title" for child in children):
        fail(f"{path.name}: missing direct <title>")
    if not any(local_name(child.tag) == "desc" for child in children):
        fail(f"{path.name}: missing direct <desc>")
    missing_ids = GROUP_IDS - ids
    if missing_ids:
        fail(f"{path.name}: missing group IDs {sorted(missing_ids)}")

    text = path.read_text(encoding="utf-8")
    searchable = " ".join(labels)
    for name in AGENT_NAMES:
        if name not in searchable:
            fail(f"{path.name}: missing agent name {name!r}")
    for specialist in SPECIALISTS:
        group = next(
            element for element in root.iter() if element.get("id") == specialist
        )
        group_text = " ".join("".join(group.itertext()).split())
        if GROUP_NAMES[specialist] not in group_text:
            fail(f"{path.name}: {specialist} missing its exact display name")
        for section in ("INPUT", "AGENT PROCESS", "OUTPUT"):
            if section not in group_text:
                fail(f"{path.name}: {specialist} missing {section}")
        if not any(
            element.get("data-from") == specialist
            and element.get("data-to") == "skillshelf-orchestrator"
            for element in root.iter()
        ):
            fail(f"{path.name}: {specialist} has no return connector")
        if any(
            element.get("data-from") == specialist
            and element.get("data-to") == "final-response"
            for element in root.iter()
        ):
            fail(f"{path.name}: {specialist} bypasses the orchestrator")

    forbidden = {
        "<script": r"<\s*script\b",
        "foreignObject": r"<\s*foreignObject\b",
        "embedded image": r"<\s*image\b",
        "remote image": r"<\s*image\b[^>]+(?:href|xlink:href)\s*=\s*[\"']https?://",
        "tracking pixel": r"<\s*image\b[^>]+(?:width|height)\s*=\s*[\"']1[\"']",
        "external font": r"(?:@import|url\()\s*[\"']?https?://",
        "base64 payload": r"data:image/[^;]+;base64,",
        "gradient": r"<\s*(?:linearGradient|radialGradient)\b",
        "event handler": r"\son[a-z]+\s*=",
    }
    for label, pattern in forbidden.items():
        if re.search(pattern, text, re.IGNORECASE):
            fail(f"{path.name}: forbidden {label}")
    return labels


def validate_readme() -> None:
    text = README.read_text(encoding="utf-8")
    required = {
        "./docs/assets/skillshelf-agent-workflow.svg",
        "./docs/assets/skillshelf-agent-workflow-dark.svg",
        "./docs/agents/WORKFLOW_MAP.md",
    }
    for reference in required:
        if reference not in text:
            fail(f"README missing {reference}")
        target = (ROOT / reference.removeprefix("./")).resolve()
        if not target.is_file() or ROOT.resolve() not in target.parents:
            fail(f"README reference does not resolve safely: {reference}")
    if not re.search(
        r'alt="SkillShelf agent workflow[^"]+final response\."', text, re.IGNORECASE
    ):
        fail("README workflow image alt text is missing or incomplete")
    if not re.search(
        r'<img\b[^>]*\bsrc="\./docs/assets/skillshelf-agent-workflow\.svg"'
        r'[^>]*\balt="[^"]+"[^>]*\bwidth="100%"',
        text,
        re.IGNORECASE | re.DOTALL,
    ):
        fail(
            "README workflow image must use the canonical source, alt text and 100% width"
        )


def validate_mermaid() -> None:
    text = MERMAID.read_text(encoding="utf-8")
    for node in (
        "USER",
        "MASTER",
        "FIND",
        "SUPER",
        "MEMORY",
        "DESIGN",
        "GOVERNOR",
        "FINAL",
    ):
        if not re.search(rf"^\s*{node}\[", text, re.MULTILINE):
            fail(f"Mermaid source missing {node} node")
    for node in ("FIND", "SUPER", "MEMORY", "DESIGN"):
        if not re.search(
            rf"^\s*MASTER\s+-->\|Bounded DelegationInput\|\s+{node}",
            text,
            re.MULTILINE,
        ):
            fail(f"Mermaid source missing MASTER outbound edge to {node}")
        if not re.search(
            rf"^\s*{node}\s+-\.->\|Structured SpecialistResult\|\s+MASTER",
            text,
            re.MULTILINE,
        ):
            fail(f"Mermaid source missing {node} return edge")
    if not re.search(
        r"^\s*MASTER\s+-->\|Bounded DelegationInput\|\s+GOVERNOR",
        text,
        re.MULTILINE,
    ):
        fail("Mermaid source missing MASTER outbound edge to GOVERNOR")
    if not re.search(
        r"^\s*GOVERNOR\s+-\.->\|Structured GovernanceResult\|\s+MASTER",
        text,
        re.MULTILINE,
    ):
        fail("Mermaid source missing governor return edge")
    if re.search(
        r"^\s*(?:FIND|SUPER|MEMORY|DESIGN|GOVERNOR)\s+[-.=]+>\|?.*FINAL",
        text,
        re.MULTILINE,
    ):
        fail("Mermaid source connects a specialist directly to FINAL")
    if not re.search(
        r"^\s*MASTER\s+==>\|Reconciled verified result\|\s+FINAL",
        text,
        re.MULTILINE,
    ):
        fail("Mermaid source missing verified MASTER to FINAL edge")


def main() -> int:
    for path in (LIGHT, DARK, MERMAID, WORKFLOW_DOC):
        if not path.is_file():
            fail(f"missing required workflow file: {path.relative_to(ROOT)}")
    light_labels = validate_svg(LIGHT)
    dark_labels = validate_svg(DARK)
    if light_labels != dark_labels:
        fail("light and dark SVG logical labels differ")
    validate_mermaid()
    validate_readme()
    print("SkillShelf agent workflow visual validation passed")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except AssertionError as exc:
        print(f"WORKFLOW VISUAL VALIDATION FAILED: {exc}", file=sys.stderr)
        raise SystemExit(1)
