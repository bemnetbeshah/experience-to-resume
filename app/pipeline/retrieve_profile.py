"""Load, normalize, and rank verified candidate evidence."""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from app.config import DATA_DIR
from app.models import CandidateProfile, JobAnalysis, ProfileItem, RetrievedProfile


def _read_json(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise ValueError(f"Missing profile data file: {path}") from exc
    except json.JSONDecodeError as exc:
        raise ValueError(f"Invalid JSON in {path}: {exc}") from exc


def _experience_item(raw: dict[str, Any]) -> ProfileItem:
    return ProfileItem(
        id=raw["id"],
        title=raw["title"],
        category="experience",
        organization=raw["company"],
        location=raw.get("location"),
        start=raw.get("start"),
        end=raw.get("end"),
        url=None,
        bullets=raw["highlights"],
        tags=raw.get("technologies", []),
    )


def _project_item(raw: dict[str, Any]) -> ProfileItem:
    return ProfileItem(
        id=raw["id"],
        title=raw["name"],
        category="project",
        organization=None,
        location=None,
        start=raw.get("start"),
        end=raw.get("end"),
        url=raw.get("url"),
        bullets=raw["highlights"],
        tags=raw.get("technologies", []),
    )


def load_profile(data_dir: Path = DATA_DIR) -> RetrievedProfile:
    candidate = CandidateProfile.model_validate(_read_json(data_dir / "profile.json"))
    experiences = _read_json(data_dir / "experiences.json")
    projects = _read_json(data_dir / "projects.json")
    skills = _read_json(data_dir / "skills.json")
    if not isinstance(experiences, list) or not isinstance(projects, list):
        raise ValueError("experiences.json and projects.json must contain arrays")
    if not isinstance(skills, dict):
        raise ValueError("skills.json must contain an object")

    items = [
        *(_experience_item(item) for item in experiences),
        *(_project_item(item) for item in projects),
    ]
    ids = [item.id for item in items]
    if len(ids) != len(set(ids)):
        raise ValueError("Experience and project ids must be unique")
    return RetrievedProfile(candidate=candidate, items=items, skills=skills)


def _terms(job: JobAnalysis) -> set[str]:
    values = [
        *job.required_skills,
        *job.preferred_skills,
        *job.keywords,
        *job.responsibilities,
    ]
    return {
        token
        for value in values
        for token in re.findall(r"[a-z0-9+#./-]+", value.lower())
        if len(token) > 1
    }


def retrieve_profile(
    job: JobAnalysis,
    data_dir: Path = DATA_DIR,
    limit: int = 10,
) -> RetrievedProfile:
    profile = load_profile(data_dir)
    job_terms = _terms(job)

    def score(item: ProfileItem) -> int:
        searchable = " ".join(
            [item.title, *item.tags, *item.bullets]
        ).lower()
        return sum(term in searchable for term in job_terms)

    ranked = sorted(profile.items, key=score, reverse=True)
    return profile.model_copy(update={"items": ranked[:limit]})
