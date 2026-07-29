#!/usr/bin/env python3
"""Generate SkillShelf's registry-driven agent workflow specification and visuals."""

from __future__ import annotations

import argparse
import html
import json
import pathlib
import re
import sys
from typing import Any

import yaml

ROOT = pathlib.Path(__file__).resolve().parents[1]
REGISTRY = ROOT / "agents" / "registry.yml"

OUTPUTS = {
    "overview_light": ROOT / "docs/assets/skillshelf-agent-workflow-overview.svg",
    "overview_dark": ROOT / "docs/assets/skillshelf-agent-workflow-overview-dark.svg",
    "full_light": ROOT / "docs/assets/skillshelf-agent-workflow.svg",
    "full_dark": ROOT / "docs/assets/skillshelf-agent-workflow-dark.svg",
    "mermaid": ROOT / "docs/diagrams/skillshelf-agent-workflow.mmd",
    "spec": ROOT / "docs/diagrams/skillshelf-agent-workflow.json",
}

THEMES = {
    "light": {
        "background": "#F6F8FB",
        "surface": "#FFFFFF",
        "master": "#E3EFF9",
        "ink": "#102A43",
        "secondary": "#334E68",
        "accent": "#075985",
        "muted": "#D9E7F2",
        "line": "#486581",
    },
    "dark": {
        "background": "#091522",
        "surface": "#13263A",
        "master": "#183B59",
        "ink": "#F5F9FC",
        "secondary": "#C7D8E6",
        "accent": "#8DD3F4",
        "muted": "#274963",
        "line": "#A8C5D8",
    },
}


def load_registry() -> dict[str, Any]:
    value = yaml.safe_load(REGISTRY.read_text(encoding="utf-8"))
    if not isinstance(value, dict) or not isinstance(value.get("agents"), list):
        raise ValueError("agents/registry.yml does not contain a valid agent registry")
    return value


def humanize(value: str) -> str:
    return value.replace("_", " ").replace("-", " ").strip().title()


def build_spec(registry: dict[str, Any] | None = None) -> dict[str, Any]:
    """Build the canonical workflow specification from the live registry."""
    registry = registry or load_registry()
    master = registry["master"]
    specialists = []
    for agent in registry["agents"]:
        capabilities = agent.get("allowed_capabilities", [])
        authority = humanize(capabilities[0]) if capabilities else "Registry Allowlist"
        specialists.append(
            {
                "id": agent["id"],
                "display_name": agent["display_name"],
                "skill": agent["skill"],
                "input_labels": [
                    "Task and success criteria",
                    "Relevant paths and context",
                    f"Authority: {authority}",
                ],
                "process_labels": [
                    f"Load {agent['skill']}",
                    f"Invoke {humanize(agent['tool_name'])}",
                    "Record tool and usage evidence",
                ],
                "output_labels": [
                    agent["output_contract"],
                    "Findings and artifacts",
                    "Tests, risks, next action",
                ],
                "output_contract": agent["output_contract"],
            }
        )

    master_id = master["id"]
    return {
        "schema_version": 1,
        "source": "agents/registry.yml",
        "master": {
            "id": master_id,
            "display_name": master["display_name"],
            "input_labels": [
                "Goal, context, constraints",
                "Files and approval authority",
            ],
            "process_labels": [
                "Route the smallest sufficient set",
                "Enforce budgets and approvals",
                "Reconcile recorded evidence",
            ],
            "output_labels": [
                master["output_contract"],
                "Verified final response",
            ],
            "output_contract": master["output_contract"],
        },
        "specialists": specialists,
        "delegation_edges": [
            {
                "from": master_id,
                "to": specialist["id"],
                "label": "Bounded DelegationInput",
            }
            for specialist in specialists
        ],
        "return_edges": [
            {
                "from": specialist["id"],
                "to": master_id,
                "label": specialist["output_contract"],
            }
            for specialist in specialists
        ],
        "final_response_edge": {
            "from": master_id,
            "to": "final-response",
            "label": "Reconciled verified result",
        },
    }


def esc(value: object) -> str:
    return html.escape(str(value), quote=True)


def split_label(value: str, maximum: int = 22) -> list[str]:
    words = value.split()
    lines: list[str] = []
    current = ""
    for word in words:
        candidate = f"{current} {word}".strip()
        if current and len(candidate) > maximum:
            lines.append(current)
            current = word
        else:
            current = candidate
    if current:
        lines.append(current)
    return lines or [value]


def split_identifier(value: str, maximum: int = 14) -> list[str]:
    """Wrap a hyphenated identifier while preserving its exact searchable text."""
    pieces = value.split("-")
    lines: list[str] = []
    current = ""
    for index, piece in enumerate(pieces):
        token = piece + ("-" if index < len(pieces) - 1 else "")
        if current and len(current + token) > maximum:
            lines.append(current)
            current = token
        else:
            current += token
    if current:
        lines.append(current)
    return lines


def text_lines(
    x: int,
    y: int,
    lines: list[str],
    *,
    size: int,
    color: str,
    background: str,
    weight: int = 500,
    line_height: int | None = None,
    anchor: str = "start",
    css_class: str = "",
) -> str:
    line_height = line_height or int(size * 1.28)
    spans = "".join(
        f'<tspan x="{x}" dy="{0 if index == 0 else line_height}">{esc(line)}</tspan>'
        for index, line in enumerate(lines)
    )
    class_attr = f' class="{esc(css_class)}"' if css_class else ""
    return (
        f'<text x="{x}" y="{y}" font-family="Segoe UI,Arial,sans-serif" '
        f'font-size="{size}" font-weight="{weight}" fill="{color}" '
        f'text-anchor="{anchor}" data-background="{background}"{class_attr}>{spans}</text>'
    )


def svg_shell(
    body: str,
    *,
    width: int,
    height: int,
    title: str,
    description: str,
    theme: dict[str, str],
) -> str:
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {width} {height}" '
        'role="img" aria-labelledby="workflow-title workflow-desc">\n'
        f'  <title id="workflow-title">{esc(title)}</title>\n'
        f'  <desc id="workflow-desc">{esc(description)}</desc>\n'
        "  <defs>\n"
        f'    <marker id="arrow-delegation" viewBox="0 0 10 10" refX="9" refY="5" '
        'markerWidth="7" markerHeight="7" orient="auto-start-reverse">'
        f'<path d="M0 0L10 5L0 10Z" fill="{theme["line"]}"/></marker>\n'
        f'    <marker id="arrow-return" viewBox="0 0 10 10" refX="9" refY="5" '
        'markerWidth="7" markerHeight="7" orient="auto-start-reverse">'
        f'<path d="M0 0L10 5L0 10Z" fill="{theme["accent"]}"/></marker>\n'
        "  </defs>\n"
        f'  <rect width="{width}" height="{height}" fill="{theme["background"]}"/>\n'
        f"{body}\n"
        "</svg>\n"
    )


def render_overview(spec: dict[str, Any], *, dark: bool = False) -> str:
    theme = THEMES["dark" if dark else "light"]
    background = theme["background"]
    body: list[str] = []
    body.append(
        text_lines(
            32,
            42,
            ["SkillShelf agent workflow"],
            size=30,
            color=theme["ink"],
            background=background,
            weight=700,
        )
    )
    body.append(
        text_lines(
            928,
            40,
            ["REGISTRY-DRIVEN"],
            size=22,
            color=theme["secondary"],
            background=background,
            weight=700,
            anchor="end",
        )
    )

    top_nodes = [
        ("user-input", "User request", 24, 80, 200, 116, theme["surface"]),
        (
            spec["master"]["id"],
            spec["master"]["display_name"],
            280,
            64,
            400,
            148,
            theme["master"],
        ),
        ("final-response", "Verified response", 736, 80, 200, 116, theme["surface"]),
    ]
    for node_id, label, x, y, width, height, fill in top_nodes:
        body.append(
            f'<g id="{esc(node_id)}" data-qa-box="true" aria-label="{esc(label)}">'
            f'<rect x="{x}" y="{y}" width="{width}" height="{height}" rx="14" '
            f'fill="{fill}" stroke="{theme["line"]}" stroke-width="2"/>'
        )
        body.append(
            text_lines(
                x + width // 2,
                y + 46,
                split_label(label, 14 if node_id == "final-response" else 22),
                size=25,
                color=theme["ink"],
                background=fill,
                weight=700,
                line_height=29,
                anchor="middle",
            )
        )
        if node_id == spec["master"]["id"]:
            body.append(
                text_lines(
                    x + width // 2,
                    y + 112,
                    ["Routes, governs, reconciles"],
                    size=22,
                    color=theme["secondary"],
                    background=fill,
                    anchor="middle",
                )
            )
        body.append("</g>")

    body.append(
        f'<g id="connections" fill="none" stroke="{theme["line"]}" stroke-width="3">'
        f'<path d="M224 138H280" marker-end="url(#arrow-delegation)" '
        f'data-from="user-input" data-to="{esc(spec["master"]["id"])}" data-kind="input"/>'
        f'<path d="M680 138H736" marker-end="url(#arrow-delegation)" '
        f'data-from="{esc(spec["master"]["id"])}" data-to="final-response" data-kind="final"/>'
        "</g>"
    )

    specialists = spec["specialists"]
    card_width = 172
    gap = 15
    start_x = 20
    card_y = 316
    card_height = 172
    body.append('<g id="specialists" aria-label="Bounded specialist agents">')
    for index, specialist in enumerate(specialists):
        x = start_x + index * (card_width + gap)
        center = x + card_width // 2
        master_start = 326 + index * 77
        body.append(
            f'<path d="M{master_start} 212V278H{center}V316" '
            f'fill="none" stroke="{theme["line"]}" stroke-width="2.5" '
            f'marker-end="url(#arrow-delegation)" data-from="{esc(spec["master"]["id"])}" '
            f'data-to="{esc(specialist["id"])}" data-kind="delegation"/>'
        )
        body.append(
            f'<path d="M{center + 11} 316V292H{master_start + 11}V212" '
            f'fill="none" stroke="{theme["accent"]}" stroke-width="2.5" stroke-dasharray="7 6" '
            f'marker-end="url(#arrow-return)" data-from="{esc(specialist["id"])}" '
            f'data-to="{esc(spec["master"]["id"])}" data-kind="return"/>'
        )
        body.append(
            f'<g id="{esc(specialist["id"])}" data-qa-box="true" '
            f'aria-label="{esc(specialist["display_name"])}">'
            f'<rect x="{x}" y="{card_y}" width="{card_width}" height="{card_height}" rx="12" '
            f'fill="{theme["surface"]}" stroke="{theme["line"]}" stroke-width="2"/>'
        )
        name_lines = split_label(specialist["display_name"], 16)[:3]
        body.append(
            text_lines(
                center,
                card_y + 40,
                name_lines,
                size=22,
                color=theme["ink"],
                background=theme["surface"],
                weight=700,
                line_height=26,
                anchor="middle",
            )
        )
        skill_lines = split_identifier(specialist["skill"])[:2]
        skill_y = card_y + 82 + (len(name_lines) - 1) * 26
        body.append(
            text_lines(
                center,
                skill_y,
                skill_lines,
                size=21,
                color=theme["secondary"],
                background=theme["surface"],
                line_height=25,
                anchor="middle",
            )
        )
        body.append("</g>")
    body.append("</g>")

    body.append(
        f'<g id="legend" data-qa-box="true">'
        f'<rect x="100" y="506" width="760" height="46" rx="8" fill="{theme["muted"]}"/>'
        + text_lines(
            480,
            536,
            ["Solid: bounded delegation  |  Dashed: structured return"],
            size=21,
            color=theme["ink"],
            background=theme["muted"],
            weight=600,
            anchor="middle",
        )
        + "</g>"
    )
    return svg_shell(
        "\n  ".join(body),
        width=960,
        height=564,
        title="SkillShelf registry-driven agent workflow overview",
        description=(
            "A user request enters the central SkillShelf Master, which delegates bounded "
            "work to registry-defined specialists, reconciles their structured returns, "
            "and produces one verified response."
        ),
        theme=theme,
    )


def render_full(spec: dict[str, Any], *, dark: bool = False) -> str:
    theme = THEMES["dark" if dark else "light"]
    background = theme["background"]
    specialists = spec["specialists"]
    card_height = 276
    card_gap = 34
    first_y = 342
    height = first_y + len(specialists) * (card_height + card_gap) + 122
    body: list[str] = []
    body.append(
        text_lines(
            40,
            48,
            ["SkillShelf agent workflow: detailed contract"],
            size=31,
            color=theme["ink"],
            background=background,
            weight=700,
        )
    )
    top_nodes = [
        ("user-input", "User request", 40, 86, 190, 126, theme["surface"]),
        (
            spec["master"]["id"],
            spec["master"]["display_name"],
            286,
            76,
            388,
            172,
            theme["master"],
        ),
        ("final-response", "Final response", 730, 86, 190, 126, theme["surface"]),
    ]
    for node_id, label, x, y, width, node_height, fill in top_nodes:
        body.append(
            f'<g id="{esc(node_id)}" data-qa-box="true" aria-label="{esc(label)}">'
            f'<rect x="{x}" y="{y}" width="{width}" height="{node_height}" rx="14" '
            f'fill="{fill}" stroke="{theme["line"]}" stroke-width="2"/>'
        )
        body.append(
            text_lines(
                x + width // 2,
                y + 46,
                split_label(label, 22),
                size=25,
                color=theme["ink"],
                background=fill,
                weight=700,
                line_height=29,
                anchor="middle",
            )
        )
        if node_id == spec["master"]["id"]:
            body.append(
                text_lines(
                    x + width // 2,
                    y + 112,
                    spec["master"]["process_labels"][:2],
                    size=21,
                    color=theme["secondary"],
                    background=fill,
                    line_height=27,
                    anchor="middle",
                )
            )
        body.append("</g>")

    body.append(
        f'<path d="M230 149H286" fill="none" stroke="{theme["line"]}" stroke-width="3" '
        f'marker-end="url(#arrow-delegation)" data-from="user-input" '
        f'data-to="{esc(spec["master"]["id"])}" data-kind="input"/>'
    )
    body.append(
        f'<path d="M674 149H730" fill="none" stroke="{theme["line"]}" stroke-width="3" '
        f'marker-end="url(#arrow-delegation)" data-from="{esc(spec["master"]["id"])}" '
        'data-to="final-response" data-kind="final"/>'
    )

    for index, specialist in enumerate(specialists):
        y = first_y + index * (card_height + card_gap)
        mid_y = y + card_height // 2
        delegate_gutter = 18 + index * 7
        return_gutter = 942 - index * 7
        body.append(
            f'<path d="M360 248H{delegate_gutter}V{mid_y}H68" fill="none" '
            f'stroke="{theme["line"]}" stroke-width="2.5" marker-end="url(#arrow-delegation)" '
            f'data-from="{esc(spec["master"]["id"])}" data-to="{esc(specialist["id"])}" '
            'data-kind="delegation"/>'
        )
        body.append(
            f'<path d="M892 {mid_y}H{return_gutter}V248H600" fill="none" '
            f'stroke="{theme["accent"]}" stroke-width="2.5" stroke-dasharray="8 7" '
            f'marker-end="url(#arrow-return)" data-from="{esc(specialist["id"])}" '
            f'data-to="{esc(spec["master"]["id"])}" data-kind="return"/>'
        )
        body.append(
            f'<g id="{esc(specialist["id"])}" data-qa-box="true" '
            f'aria-label="{esc(specialist["display_name"])}">'
            f'<rect x="68" y="{y}" width="824" height="{card_height}" rx="14" '
            f'fill="{theme["surface"]}" stroke="{theme["line"]}" stroke-width="2"/>'
        )
        body.append(
            text_lines(
                94,
                y + 40,
                [specialist["display_name"]],
                size=26,
                color=theme["ink"],
                background=theme["surface"],
                weight=700,
            )
        )
        body.append(
            text_lines(
                866,
                y + 39,
                [f'{specialist["skill"]} / {specialist["output_contract"]}'],
                size=21,
                color=theme["secondary"],
                background=theme["surface"],
                weight=600,
                anchor="end",
            )
        )
        body.append(
            f'<path d="M68 {y + 62}H892M342 {y + 62}V{y + 258}M617 {y + 62}V{y + 258}" '
            f'fill="none" stroke="{theme["muted"]}" stroke-width="2"/>'
        )
        columns = (
            ("INPUT", specialist["input_labels"], 94),
            ("PROCESS", specialist["process_labels"], 368),
            ("OUTPUT", specialist["output_labels"], 643),
        )
        for heading, labels, x in columns:
            body.append(
                text_lines(
                    x,
                    y + 92,
                    [heading],
                    size=21,
                    color=theme["accent"],
                    background=theme["surface"],
                    weight=700,
                )
            )
            for label_index, label in enumerate(labels):
                wrapped = split_label(label, 23)[:2]
                body.append(
                    text_lines(
                        x,
                        y + 123 + label_index * 56,
                        wrapped,
                        size=21,
                        color=theme["secondary"],
                        background=theme["surface"],
                        line_height=23,
                    )
                )
        body.append("</g>")

    legend_y = first_y + len(specialists) * (card_height + card_gap) + 8
    body.append(
        f'<g id="legend" data-qa-box="true">'
        f'<rect x="70" y="{legend_y}" width="820" height="52" rx="10" fill="{theme["muted"]}"/>'
        + text_lines(
            480,
            legend_y + 34,
            ["Solid: DelegationInput  |  Dashed: structured result  |  Master owns final response"],
            size=21,
            color=theme["ink"],
            background=theme["muted"],
            weight=600,
            anchor="middle",
        )
        + "</g>"
    )
    return svg_shell(
        "\n  ".join(body),
        width=960,
        height=height,
        title="SkillShelf detailed registry-driven agent workflow",
        description=(
            "The live registry defines the SkillShelf Master and every specialist, "
            "including skills, bounded inputs, processes, output contracts, delegation "
            "edges, structured return edges, and the single final-response edge."
        ),
        theme=theme,
    )


def mermaid_id(value: str) -> str:
    return re.sub(r"[^A-Za-z0-9_]", "_", value).upper()


def render_mermaid(spec: dict[str, Any]) -> str:
    master_alias = mermaid_id(spec["master"]["id"])
    lines = [
        "%% Generated from agents/registry.yml. Do not edit by hand.",
        "flowchart TB",
        '    USER["User request<br/>Goal, context, constraints, files, authority"]',
        f'    {master_alias}["{spec["master"]["display_name"]}<br/>{spec["master"]["output_contract"]}"]',
    ]
    for specialist in spec["specialists"]:
        alias = mermaid_id(specialist["id"])
        lines.append(
            f'    {alias}["{specialist["display_name"]}<br/>{specialist["skill"]}'
            f'<br/>{specialist["output_contract"]}"]'
        )
    lines.extend(
        [
            '    FINAL["Final structured response<br/>Verified evidence, tests, usage, risks"]',
            f"    USER -->|Complete request| {master_alias}",
        ]
    )
    for edge in spec["delegation_edges"]:
        lines.append(
            f'    {mermaid_id(edge["from"])} -->|{edge["label"]}| {mermaid_id(edge["to"])}'
        )
    for edge in spec["return_edges"]:
        lines.append(
            f'    {mermaid_id(edge["from"])} -.->|{edge["label"]}| {mermaid_id(edge["to"])}'
        )
    final = spec["final_response_edge"]
    lines.append(f'    {master_alias} ==>|{final["label"]}| FINAL')
    return "\n".join(lines) + "\n"


def build_outputs() -> dict[pathlib.Path, str]:
    spec = build_spec()
    return {
        OUTPUTS["overview_light"]: render_overview(spec),
        OUTPUTS["overview_dark"]: render_overview(spec, dark=True),
        OUTPUTS["full_light"]: render_full(spec),
        OUTPUTS["full_dark"]: render_full(spec, dark=True),
        OUTPUTS["mermaid"]: render_mermaid(spec),
        OUTPUTS["spec"]: json.dumps(spec, indent=2, ensure_ascii=False) + "\n",
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--check",
        action="store_true",
        help="Fail if generated assets do not match the live registry.",
    )
    args = parser.parse_args()
    drift: list[str] = []
    outputs = build_outputs()
    for path, content in outputs.items():
        if args.check:
            if not path.is_file() or path.read_text(encoding="utf-8") != content:
                drift.append(path.relative_to(ROOT).as_posix())
        else:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(content, encoding="utf-8", newline="\n")
    if drift:
        print("agent workflow visual drift: " + ", ".join(drift), file=sys.stderr)
        return 1
    action = "validated" if args.check else "generated"
    print(f"{action} {len(outputs)} registry-driven workflow files")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
