"""Turn an unstructured job posting into targeting criteria."""

from __future__ import annotations

import json
from pathlib import Path

from app.config import DATA_DIR
from app.llm import ask_structured
from app.models import JobAnalysis


def analyze_job(job_description: str) -> JobAnalysis:
    if not job_description.strip():
        raise ValueError("Job description cannot be empty")

    return ask_structured(
        instructions=(
            "Analyze a job description for resume tailoring. Extract only what "
            "the posting supports. Use an empty list for absent skill groups, "
            "null when the company is unknown, and a concise resume angle."
        ),
        input_text=job_description,
        schema=JobAnalysis,
    )


def _normalize(text: str) -> str:
    return " ".join(text.lower().split())


def load_role_preset(
    role: str,
    data_dir: Path = DATA_DIR,
) -> JobAnalysis | None:
    """Return a deterministic, curated JobAnalysis for a known role, or None.

    Presets live in ``data/roles.json``. Matching is case- and
    whitespace-insensitive against each preset's ``match`` aliases.
    """
    if not role.strip():
        raise ValueError("Role cannot be empty")

    path = data_dir / "roles.json"
    if not path.exists():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ValueError(f"Invalid JSON in {path}: {exc}") from exc

    target = _normalize(role)
    for preset in data.get("roles", []):
        aliases = {_normalize(alias) for alias in preset.get("match", [])}
        if target in aliases:
            return JobAnalysis.model_validate(preset["analysis"])
    return None


def analyze_role(role: str) -> JobAnalysis:
    if not role.strip():
        raise ValueError("Role cannot be empty")

    return ask_structured(
        instructions=(
            "You are given only a target job role or title, not a full posting. "
            "Produce realistic resume-targeting criteria for that role based on "
            "common industry expectations: the canonical role title, typical "
            "required and preferred skills, core responsibilities, ATS keywords, "
            "and a concise resume angle. Leave company null and do not invent a "
            "specific employer."
        ),
        input_text=f"Target role: {role.strip()}",
        schema=JobAnalysis,
    )
