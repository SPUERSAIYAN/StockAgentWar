from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[1]
PROMPTS_DIR = PROJECT_ROOT / "prompts"


@dataclass(frozen=True)
class PromptTemplate:
    system: str
    user: str

    def render(self, values: dict[str, Any]) -> tuple[str, str]:
        mapping = SafeFormatDict(values)
        return self.system.format_map(mapping), self.user.format_map(mapping)


class SafeFormatDict(dict[str, Any]):
    def __missing__(self, key: str) -> str:
        return "{" + key + "}"


def load_agent_prompt(file_name: str) -> PromptTemplate:
    prompt_path = PROMPTS_DIR / file_name
    return load_prompt_template(prompt_path)


def load_prompt_text(file_name: str, reference_files: list[str] | tuple[str, ...] = ()) -> str:
    prompt_path = PROMPTS_DIR / file_name
    sections = [prompt_path.read_text(encoding="utf-8").strip()]
    for reference_file in reference_files:
        reference_path = PROMPTS_DIR / reference_file
        reference_text = reference_path.read_text(encoding="utf-8").strip()
        sections.extend(
            [
                "",
                "---",
                "",
                f"# Reference: {reference_file}",
                "",
                reference_text,
            ]
        )
    return "\n".join(sections).strip()


def load_prompt_template(prompt_path: Path) -> PromptTemplate:
    text = prompt_path.read_text(encoding="utf-8")
    sections: dict[str, list[str]] = {"system": [], "user": []}
    current: str | None = None

    for line in text.splitlines():
        heading = line.strip().lower()
        if heading in {"## system", "## system prompt"}:
            current = "system"
            continue
        if heading in {"## user", "## user prompt"}:
            current = "user"
            continue
        if current:
            sections[current].append(line)

    system = "\n".join(sections["system"]).strip()
    user = "\n".join(sections["user"]).strip()
    if not system or not user:
        raise ValueError(f"Prompt file must contain both ## System and ## User sections: {prompt_path}")
    return PromptTemplate(system=system, user=user)
