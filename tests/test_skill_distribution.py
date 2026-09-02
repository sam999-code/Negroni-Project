import json
import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SKILL = ROOT / "skills" / "negroni-governed-agents" / "SKILL.md"


def _frontmatter(text: str) -> dict[str, str]:
    match = re.match(r"\A---\n(.*?)\n---\n", text, re.DOTALL)
    assert match is not None
    fields: dict[str, str] = {}
    for line in match.group(1).splitlines():
        key, value = line.split(":", 1)
        fields[key.strip()] = value.strip()
    return fields


def test_skill_uses_portable_frontmatter() -> None:
    fields = _frontmatter(SKILL.read_text(encoding="utf-8"))
    assert fields["name"] == "negroni-governed-agents"
    assert set(fields) == {"name", "description"}
    assert len(fields["description"]) <= 60
    assert fields["description"].endswith(".")


def test_skill_references_exist() -> None:
    skill_dir = SKILL.parent
    assert (skill_dir / "references" / "governance-patterns.md").is_file()
    assert (skill_dir / "references" / "review-checklist.md").is_file()
    assert (skill_dir / "agents" / "openai.yaml").is_file()


def test_claude_manifests_are_valid_and_versioned() -> None:
    plugin = json.loads((ROOT / ".claude-plugin" / "plugin.json").read_text(encoding="utf-8"))
    marketplace = json.loads((ROOT / ".claude-plugin" / "marketplace.json").read_text(encoding="utf-8"))
    assert plugin["name"] == "negroni-project"
    assert plugin["version"] == marketplace["version"]
    assert marketplace["plugins"][0]["source"] == "./"


def test_universal_prompt_preserves_authority_boundary() -> None:
    prompt = (ROOT / "UNIVERSAL_PROMPT.md").read_text(encoding="utf-8")
    assert "Never infer EXECUTE" in prompt
    assert "Loading these instructions never grants" in prompt
    assert "VERDICT: READY | READY_WITH_LIMITS | BLOCKED" in prompt


def test_installation_covers_native_and_fallback_hosts() -> None:
    guide = (ROOT / "docs" / "INSTALLATION.md").read_text(encoding="utf-8")
    for host in ("Claude Code", "Hermes Agent", "OpenAI Codex", "Other LLMs"):
        assert f"## {host}" in guide

