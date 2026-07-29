#!/usr/bin/env python3
"""Validate SkillShelf's registry-driven workflow specification and rendered visuals."""

from __future__ import annotations

import argparse
import html
import importlib.util
import json
import os
import pathlib
import re
import shutil
import subprocess
import sys
import tempfile
import xml.etree.ElementTree as ET
from typing import Any

import yaml

ROOT = pathlib.Path(__file__).resolve().parents[1]
REGISTRY = ROOT / "agents/registry.yml"
SPEC = ROOT / "docs/diagrams/skillshelf-agent-workflow.json"
OVERVIEW_LIGHT = ROOT / "docs/assets/skillshelf-agent-workflow-overview.svg"
OVERVIEW_DARK = ROOT / "docs/assets/skillshelf-agent-workflow-overview-dark.svg"
FULL_LIGHT = ROOT / "docs/assets/skillshelf-agent-workflow.svg"
FULL_DARK = ROOT / "docs/assets/skillshelf-agent-workflow-dark.svg"
MERMAID = ROOT / "docs/diagrams/skillshelf-agent-workflow.mmd"
WORKFLOW_DOC = ROOT / "docs/agents/WORKFLOW_MAP.md"
README = ROOT / "README.md"
WIDTHS = (1600, 1200, 900, 600, 320)


def fail(message: str) -> None:
    raise AssertionError(message)


def local_name(tag: str) -> str:
    return tag.rsplit("}", 1)[-1]


def load_generator() -> Any:
    path = ROOT / "scripts/generate-agent-workflow-visual.py"
    module_spec = importlib.util.spec_from_file_location("workflow_visual_generator", path)
    if module_spec is None or module_spec.loader is None:
        fail("unable to load workflow visual generator")
    module = importlib.util.module_from_spec(module_spec)
    module_spec.loader.exec_module(module)
    return module


def parse_svg(path: pathlib.Path) -> tuple[ET.Element, list[ET.Element]]:
    try:
        root = ET.parse(path).getroot()
    except (ET.ParseError, OSError) as exc:
        fail(f"{path.relative_to(ROOT)} is not valid SVG: {exc}")
    ids = [element.get("id") for element in root.iter() if element.get("id")]
    if len(ids) != len(set(ids)):
        fail(f"{path.name}: duplicate SVG IDs")
    return root, list(root.iter())


def text_content(element: ET.Element) -> str:
    return " ".join("".join(element.itertext()).split())


def logical_fingerprint(path: pathlib.Path) -> dict[str, Any]:
    root, elements = parse_svg(path)
    groups = {
        element.get("id"): element.get("aria-label")
        for element in elements
        if local_name(element.tag) == "g" and element.get("id")
    }
    edges = sorted(
        (
            element.get("data-kind"),
            element.get("data-from"),
            element.get("data-to"),
        )
        for element in elements
        if element.get("data-from") and element.get("data-to")
    )
    title = next(
        (text_content(child) for child in list(root) if local_name(child.tag) == "title"),
        "",
    )
    description = next(
        (text_content(child) for child in list(root) if local_name(child.tag) == "desc"),
        "",
    )
    return {
        "groups": groups,
        "edges": edges,
        "title": re.sub(r"\b(?:light|dark)\b", "", title, flags=re.IGNORECASE).strip(),
        "description": description,
    }


def validate_svg(path: pathlib.Path, registry: dict[str, Any], *, detailed: bool) -> None:
    root, elements = parse_svg(path)
    children = list(root)
    if not any(local_name(child.tag) == "title" for child in children):
        fail(f"{path.name}: missing direct <title>")
    if not any(local_name(child.tag) == "desc" for child in children):
        fail(f"{path.name}: missing direct <desc>")
    if root.get("role") != "img" or not root.get("aria-labelledby"):
        fail(f"{path.name}: missing accessible image semantics")

    ids = {element.get("id") for element in elements if element.get("id")}
    master_id = registry["master"]["id"]
    required_ids = {
        "user-input",
        master_id,
        "final-response",
        "legend",
        *(agent["id"] for agent in registry["agents"]),
    }
    missing = required_ids - ids
    if missing:
        fail(f"{path.name}: missing registry node IDs {sorted(missing)}")

    searchable = " ".join(
        filter(
            None,
            [
                *(text_content(element) for element in elements),
                *(element.get("aria-label") for element in elements),
            ],
        )
    )
    if registry["master"]["display_name"] not in searchable:
        fail(f"{path.name}: missing master display name")
    for agent in registry["agents"]:
        for value_name in ("display_name", "skill"):
            if agent[value_name] not in searchable:
                fail(f"{path.name}: missing registry {value_name} {agent[value_name]!r}")
        if detailed and agent["output_contract"] not in searchable:
            fail(f"{path.name}: missing output contract {agent['output_contract']!r}")
        outbound = [
            element
            for element in elements
            if element.get("data-kind") == "delegation"
            and element.get("data-from") == master_id
            and element.get("data-to") == agent["id"]
        ]
        returned = [
            element
            for element in elements
            if element.get("data-kind") == "return"
            and element.get("data-from") == agent["id"]
            and element.get("data-to") == master_id
        ]
        if len(outbound) != 1 or len(returned) != 1:
            fail(f"{path.name}: invalid outbound/return edges for {agent['id']}")
        if any(
            element.get("data-from") == agent["id"]
            and element.get("data-to") == "final-response"
            for element in elements
        ):
            fail(f"{path.name}: {agent['id']} bypasses the master")
    final_edges = [
        element
        for element in elements
        if element.get("data-kind") == "final"
        and element.get("data-from") == master_id
        and element.get("data-to") == "final-response"
    ]
    if len(final_edges) != 1:
        fail(f"{path.name}: expected exactly one master-to-final edge")

    text = path.read_text(encoding="utf-8")
    forbidden = {
        "script": r"<\s*script\b",
        "foreignObject": r"<\s*foreignObject\b",
        "embedded image": r"<\s*image\b",
        "remote resource": r"(?:href|url\()\s*[\"']?https?://",
        "base64 payload": r"data:image/[^;]+;base64,",
        "event handler": r"\son[a-z]+\s*=",
    }
    for label, pattern in forbidden.items():
        if re.search(pattern, text, re.IGNORECASE):
            fail(f"{path.name}: forbidden {label}")


def validate_spec(registry: dict[str, Any], generator: Any) -> dict[str, Any]:
    try:
        actual = json.loads(SPEC.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        fail(f"invalid canonical workflow specification: {exc}")
    expected = generator.build_spec(registry)
    if actual != expected:
        fail("canonical workflow specification has drifted from agents/registry.yml")
    if actual["master"]["id"] != registry["master"]["id"]:
        fail("canonical workflow master ID differs from the live registry")
    if len(actual["specialists"]) != len(registry["agents"]):
        fail("canonical workflow specialist count differs from the live registry")
    required = {
        "id",
        "display_name",
        "skill",
        "input_labels",
        "process_labels",
        "output_labels",
        "output_contract",
    }
    for specialist in actual["specialists"]:
        if required - specialist.keys():
            fail(f"canonical workflow specialist is incomplete: {specialist.get('id')}")
    return actual


def validate_generated_drift(generator: Any) -> None:
    drift = [
        path.relative_to(ROOT).as_posix()
        for path, expected in generator.build_outputs().items()
        if not path.is_file() or path.read_text(encoding="utf-8") != expected
    ]
    if drift:
        fail("generated workflow file drift: " + ", ".join(drift))


def validate_mermaid(registry: dict[str, Any], spec: dict[str, Any]) -> None:
    text = MERMAID.read_text(encoding="utf-8")
    if not text.startswith("%% Generated from agents/registry.yml."):
        fail("Mermaid source does not declare its registry origin")
    generator = load_generator()
    for agent in registry["agents"]:
        alias = generator.mermaid_id(agent["id"])
        if not re.search(rf"^\s*{re.escape(alias)}\[", text, re.MULTILINE):
            fail(f"Mermaid source missing registry agent {agent['id']}")
        delegation = next(edge for edge in spec["delegation_edges"] if edge["to"] == agent["id"])
        returned = next(edge for edge in spec["return_edges"] if edge["from"] == agent["id"])
        master_alias = generator.mermaid_id(spec["master"]["id"])
        if (
            f'{master_alias} -->|{delegation["label"]}| {alias}' not in text
            or f'{alias} -.->|{returned["label"]}| {master_alias}' not in text
        ):
            fail(f"Mermaid source has incomplete edges for {agent['id']}")
        if re.search(rf"^\s*{re.escape(alias)}\s+[-.=]+>.*FINAL", text, re.MULTILINE):
            fail(f"Mermaid source lets {agent['id']} bypass the master")


def validate_document_references() -> None:
    readme = README.read_text(encoding="utf-8")
    required_readme = {
        "./docs/assets/skillshelf-agent-workflow-overview.svg",
        "./docs/assets/skillshelf-agent-workflow-overview-dark.svg",
        "./docs/agents/WORKFLOW_MAP.md",
    }
    for reference in required_readme:
        if reference not in readme:
            fail(f"README missing {reference}")
        target = (ROOT / reference.removeprefix("./")).resolve()
        if not target.is_file() or ROOT.resolve() not in target.parents:
            fail(f"README reference does not resolve safely: {reference}")
    if "./docs/assets/skillshelf-agent-workflow.svg" in readme:
        fail("README must embed the concise overview, not the full workflow diagram")
    if not re.search(
        r'alt="SkillShelf agent workflow[^"]+final response\."', readme, re.IGNORECASE
    ):
        fail("README workflow image alt text is missing or incomplete")
    workflow = WORKFLOW_DOC.read_text(encoding="utf-8")
    if "../assets/skillshelf-agent-workflow.svg" not in workflow:
        fail("detailed workflow document does not link to the full diagram")
    if "../diagrams/skillshelf-agent-workflow.json" not in workflow:
        fail("detailed workflow document does not link to the canonical JSON")


def find_browser() -> pathlib.Path | None:
    configured = os.environ.get("SKILLSHELF_VISUAL_RENDERER")
    candidates = [
        configured,
        shutil.which("google-chrome"),
        shutil.which("google-chrome-stable"),
        shutil.which("chromium"),
        shutil.which("chromium-browser"),
        shutil.which("chrome"),
        shutil.which("msedge"),
        r"C:\Program Files\Google\Chrome\Application\chrome.exe",
        r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
    ]
    for candidate in candidates:
        if candidate and pathlib.Path(candidate).is_file():
            return pathlib.Path(candidate)
    return None


def qa_document(svg: str, widths: tuple[int, ...]) -> str:
    rendered = "\n".join(
        f'<section style="width:{width}px">'
        + svg.replace("<svg ", f'<svg data-qa-width="{width}" ', 1)
        + "</section>"
        for width in widths
    )
    return f"""<!doctype html>
<html><head><meta charset="utf-8"><style>
html,body{{margin:0;padding:0;background:#fff}}
svg{{display:block;width:100%;height:auto}}
#qa{{display:none}}
</style></head><body>
{rendered}
<pre id="qa"></pre>
<script>
(() => {{
 const results = [...document.querySelectorAll("svg")].map(svg => {{
  const view = svg.viewBox.baseVal;
  const scale = svg.getBoundingClientRect().width / view.width;
  const texts = [...svg.querySelectorAll("text")];
  const paths = [...svg.querySelectorAll("path[data-from][data-to]")];
  const violations = [];
  const contrast = (a, b) => {{
    const rgb = value => {{
      let match;
      if (value.startsWith("#")) {{
        const hex = value.slice(1);
        match = [0, 2, 4].map(offset => parseInt(hex.slice(offset, offset + 2), 16));
      }} else {{
        match = value.match(/[\\d.]+/g).map(Number);
      }}
      return match.slice(0, 3).map(channel => {{
        channel /= 255;
        return channel <= .04045 ? channel / 12.92 : ((channel + .055) / 1.055) ** 2.4;
      }});
    }};
    const lum = value => {{ const c = rgb(value); return .2126*c[0]+.7152*c[1]+.0722*c[2]; }};
    const values = [lum(a), lum(b)].sort((x, y) => y - x);
    return (values[0] + .05) / (values[1] + .05);
  }};
  for (const node of [...texts, ...svg.querySelectorAll("[data-qa-box]")]) {{
    const box = node.getBBox();
    if (box.x < -0.5 || box.y < -0.5 || box.x + box.width > view.width + .5 ||
        box.y + box.height > view.height + .5) {{
      violations.push(`outside viewBox: ${{node.id || node.textContent.trim()}}`);
    }}
  }}
  for (const group of svg.querySelectorAll("[data-qa-box]")) {{
    const frame = group.querySelector("rect");
    if (!frame) continue;
    const boundary = frame.getBBox();
    for (const node of group.querySelectorAll("text")) {{
      const box = node.getBBox();
      if (box.x < boundary.x + 3 || box.y < boundary.y + 3 ||
          box.x + box.width > boundary.x + boundary.width - 3 ||
          box.y + box.height > boundary.y + boundary.height - 3) {{
        violations.push(`text clipped by node: ${{group.id}} / ${{node.textContent.trim()}}`);
      }}
    }}
  }}
  for (const node of texts) {{
    const style = getComputedStyle(node);
    const effective = parseFloat(style.fontSize) * scale;
    if (effective < 7 - .05) violations.push(`font below 7px: ${{node.textContent.trim()}} (${{effective}})`);
    const background = node.dataset.background;
    if (!background || contrast(style.fill, background) < 4.5) {{
      violations.push(`contrast below 4.5: ${{node.textContent.trim()}}`);
    }}
  }}
  for (let first = 0; first < texts.length; first++) {{
    const a = texts[first].getBBox();
    for (let second = first + 1; second < texts.length; second++) {{
      const b = texts[second].getBBox();
      const overlapX = Math.min(a.x+a.width,b.x+b.width)-Math.max(a.x,b.x);
      const overlapY = Math.min(a.y+a.height,b.y+b.height)-Math.max(a.y,b.y);
      if (overlapX > 1 && overlapY > 1) {{
        violations.push(`overlapping text: ${{texts[first].textContent.trim()}} / ${{texts[second].textContent.trim()}}`);
      }}
    }}
  }}
  for (const path of paths) {{
    const length = path.getTotalLength();
    for (const text of texts) {{
      const box = text.getBBox();
      let intersects = false;
      for (let at = 5; at < length - 5; at += 4) {{
        const point = path.getPointAtLength(at);
        if (point.x >= box.x-2 && point.x <= box.x+box.width+2 &&
            point.y >= box.y-2 && point.y <= box.y+box.height+2) {{
          intersects = true; break;
        }}
      }}
      if (intersects) {{
        violations.push(`connector crosses text: ${{path.dataset.from}} -> ${{path.dataset.to}} / ${{text.textContent.trim()}}`);
      }}
    }}
  }}
  return {{
    requestedWidth: Number(svg.dataset.qaWidth),
    renderedWidth: svg.getBoundingClientRect().width,
    renderedHeight: svg.getBoundingClientRect().height,
    textCount: texts.length,
    violations
  }};
  }});
  document.querySelector("#qa").textContent = JSON.stringify(results);
}})();
</script></body></html>"""


def render_checks(
    path: pathlib.Path, widths: tuple[int, ...], browser: pathlib.Path
) -> list[dict[str, Any]]:
    with tempfile.TemporaryDirectory(
        prefix="skillshelf-visual-qa-", ignore_cleanup_errors=True
    ) as directory:
        document = pathlib.Path(directory) / "render.html"
        document.write_text(
            qa_document(path.read_text(encoding="utf-8"), widths), encoding="utf-8"
        )
        command = [
            str(browser),
            "--headless=new",
            "--disable-gpu",
            "--disable-background-mode",
            "--disable-background-networking",
            "--disable-dev-shm-usage",
            "--no-sandbox",
            "--no-first-run",
            "--hide-scrollbars",
            f"--user-data-dir={pathlib.Path(directory) / 'browser-profile'}",
            f"--window-size={max(widths)},3200",
            "--dump-dom",
            document.resolve().as_uri(),
        ]
        stdout_path = pathlib.Path(directory) / "browser-stdout.txt"
        stderr_path = pathlib.Path(directory) / "browser-stderr.txt"
        try:
            with stdout_path.open("w", encoding="utf-8") as stdout, stderr_path.open(
                "w", encoding="utf-8"
            ) as stderr:
                completed = subprocess.run(
                    command,
                    stdout=stdout,
                    stderr=stderr,
                    timeout=60,
                    check=False,
                )
        except subprocess.TimeoutExpired:
            fail(f"{path.name} renderer timed out")
        stdout_text = stdout_path.read_text(encoding="utf-8", errors="replace")
        stderr_text = stderr_path.read_text(encoding="utf-8", errors="replace")
        if completed.returncode:
            fail(
                f"{path.name} renderer failed at {width}px: "
                + (stderr_text.strip() or f"exit {completed.returncode}")
            )
        match = re.search(r'<pre id="qa">(.*?)</pre>', stdout_text, re.DOTALL)
        if not match:
            fail(f"{path.name} renderer returned no QA payload")
        try:
            results = json.loads(html.unescape(match.group(1)))
        except json.JSONDecodeError as exc:
            fail(f"{path.name} renderer returned invalid QA payload: {exc}")
        if [result["requestedWidth"] for result in results] != list(widths):
            fail(f"{path.name} renderer omitted a requested width")
        for result in results:
            width = result["requestedWidth"]
            if abs(result["renderedWidth"] - width) > 1:
                fail(f"{path.name} did not fill its {width}px render surface")
            if result["violations"]:
                fail(f"{path.name} render at {width}px: {result['violations'][0]}")
        return results


def validate_rendered_assets() -> int:
    browser = find_browser()
    if browser is None:
        fail(
            "no supported headless Chromium renderer found; set SKILLSHELF_VISUAL_RENDERER"
        )
    checks = 0
    for path in (OVERVIEW_LIGHT, FULL_LIGHT):
        checks += len(render_checks(path, WIDTHS, browser))
    for path in (OVERVIEW_DARK, FULL_DARK):
        checks += len(render_checks(path, (1600, 320), browser))
    return checks


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--skip-render",
        action="store_true",
        help="Run structural and drift validation without launching Chromium.",
    )
    args = parser.parse_args()
    registry = yaml.safe_load(REGISTRY.read_text(encoding="utf-8"))
    generator = load_generator()
    spec = validate_spec(registry, generator)
    validate_generated_drift(generator)
    validate_svg(OVERVIEW_LIGHT, registry, detailed=False)
    validate_svg(OVERVIEW_DARK, registry, detailed=False)
    validate_svg(FULL_LIGHT, registry, detailed=True)
    validate_svg(FULL_DARK, registry, detailed=True)
    if logical_fingerprint(OVERVIEW_LIGHT) != logical_fingerprint(OVERVIEW_DARK):
        fail("light and dark overview SVGs are not logically equivalent")
    if logical_fingerprint(FULL_LIGHT) != logical_fingerprint(FULL_DARK):
        fail("light and dark detailed SVGs are not logically equivalent")
    validate_mermaid(registry, spec)
    validate_document_references()
    render_count = 0 if args.skip_render else validate_rendered_assets()
    print(
        "SkillShelf registry-driven workflow validation passed: "
        f"{len(registry['agents'])} specialists, {render_count} rendered viewports"
    )
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except AssertionError as exc:
        print(f"WORKFLOW VISUAL VALIDATION FAILED: {exc}", file=sys.stderr)
        raise SystemExit(1)
