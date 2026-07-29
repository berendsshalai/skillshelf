import importlib.util
import json
import pathlib
import xml.etree.ElementTree as ET

import yaml

ROOT = pathlib.Path(__file__).parents[1]


def load_script(name: str):
    path = ROOT / "scripts" / name
    spec = importlib.util.spec_from_file_location(name.replace("-", "_"), path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_workflow_spec_is_registry_driven_and_complete():
    generator = load_script("generate-agent-workflow-visual.py")
    registry = yaml.safe_load((ROOT / "agents/registry.yml").read_text(encoding="utf-8"))
    workflow = json.loads(
        (ROOT / "docs/diagrams/skillshelf-agent-workflow.json").read_text(
            encoding="utf-8"
        )
    )
    assert workflow == generator.build_spec(registry)
    assert workflow["master"]["id"] == registry["master"]["id"]
    assert [item["id"] for item in workflow["specialists"]] == [
        item["id"] for item in registry["agents"]
    ]
    for item in workflow["specialists"]:
        assert item["input_labels"]
        assert item["process_labels"]
        assert item["output_labels"]
        assert item["output_contract"]
    assert len(workflow["delegation_edges"]) == len(registry["agents"])
    assert len(workflow["return_edges"]) == len(registry["agents"])
    assert workflow["final_response_edge"]["from"] == registry["master"]["id"]


def test_workflow_generated_files_have_no_drift():
    generator = load_script("generate-agent-workflow-visual.py")
    first = generator.build_outputs()
    second = generator.build_outputs()
    assert first == second
    for path, expected in first.items():
        assert path.read_text(encoding="utf-8") == expected


def test_workflow_svg_pairs_are_logically_equivalent():
    validator = load_script("validate-agent-workflow-visual.py")
    pairs = (
        (
            ROOT / "docs/assets/skillshelf-agent-workflow-overview.svg",
            ROOT / "docs/assets/skillshelf-agent-workflow-overview-dark.svg",
        ),
        (
            ROOT / "docs/assets/skillshelf-agent-workflow.svg",
            ROOT / "docs/assets/skillshelf-agent-workflow-dark.svg",
        ),
    )
    for light, dark in pairs:
        assert validator.logical_fingerprint(light) == validator.logical_fingerprint(
            dark
        )
        assert ET.parse(light).getroot().get("role") == "img"
        assert ET.parse(dark).getroot().get("role") == "img"


def test_workflow_readme_uses_concise_overview():
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    assert "./docs/assets/skillshelf-agent-workflow-overview.svg" in readme
    assert "./docs/assets/skillshelf-agent-workflow-overview-dark.svg" in readme
    assert 'src="./docs/assets/skillshelf-agent-workflow.svg"' not in readme
