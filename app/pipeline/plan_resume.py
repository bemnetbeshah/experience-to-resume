"""Select grounded evidence and define the one-page resume strategy."""

from __future__ import annotations

from app.llm import ask_structured
from app.models import JobAnalysis, ResumePlan, RetrievedProfile


def plan_resume(
    job: JobAnalysis,
    profile: RetrievedProfile,
    pinned_ids: "list[str] | None" = None,
    emphasis: str = "",
) -> ResumePlan:
    pinned_ids = pinned_ids or []
    pin_note = (
        f" You MUST include these item IDs (feature them when they fit the angle, "
        f"otherwise place them in additional): {pinned_ids}."
        if pinned_ids
        else ""
    )
    emphasis_note = (
        f" Emphasize this angle when choosing summary_angle and prioritizing items, "
        f"featuring items that evidence it: {emphasis.strip()}."
        if emphasis.strip()
        else ""
    )
    plan = ask_structured(
        instructions=(
            "Create a one-page resume plan using only the supplied profile. "
            "Select item IDs exactly as written and include only skills present "
            "in the supplied skills inventory. Do not invent facts. Aim to fill a "
            "single US Letter page without overflowing, using two tiers: "
            "'featured_item_ids' are the 3 or 4 most job-relevant items (each gets "
            "two or three bullets), and 'additional_item_ids' are further relevant "
            "items shown as a single compact line each to demonstrate breadth. An "
            "item ID may appear in only one tier. Prioritize the job's required "
            "skills and responsibilities, and prefer recent, high-relevance items. "
            "Choose at most 12 skills for skills_to_show." + pin_note + emphasis_note
        ),
        input_text=(
            f"JOB:\n{job.model_dump_json(indent=2)}\n\n"
            f"PROFILE:\n{profile.model_dump_json(indent=2)}"
        ),
        schema=ResumePlan,
    )
    valid_ids = {item.id for item in profile.items}
    invalid_ids = set(plan.selected_item_ids) - valid_ids
    if invalid_ids:
        raise ValueError(f"Resume plan selected unknown profile IDs: {invalid_ids}")
    if not plan.featured_item_ids:
        raise ValueError("Resume plan must feature at least one item")
    overlap = set(plan.featured_item_ids) & set(plan.additional_item_ids)
    if overlap:
        raise ValueError(f"Items appear in both tiers: {overlap}")
    allowed_skills = {
        skill.lower()
        for values in profile.skills.values()
        for skill in values
    }
    invalid_skills = {
        skill for skill in plan.skills_to_show if skill.lower() not in allowed_skills
    }
    if invalid_skills:
        raise ValueError(f"Resume plan selected unsupported skills: {invalid_skills}")

    # Guarantee pinned items are in the plan; add any the planner skipped to the
    # additional tier so they at least appear as a compact line.
    selected = set(plan.selected_item_ids)
    missing_pins = [pid for pid in pinned_ids if pid not in selected]
    if missing_pins:
        plan = plan.model_copy(
            update={"additional_item_ids": [*plan.additional_item_ids, *missing_pins]}
        )
    return plan
