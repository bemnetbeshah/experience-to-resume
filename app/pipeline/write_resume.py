"""Write a concise resume from a validated plan and source evidence."""

from __future__ import annotations

from collections import OrderedDict

from app.llm import ask_structured
from app.models import (
    JobAnalysis,
    ResumeBullet,
    ResumeContent,
    ResumeDraft,
    ResumePlan,
    ResumeSection,
    RetrievedProfile,
)


def _compact_section_for(source) -> ResumeSection:
    """Build a deterministic one-line section from a source item's own facts."""
    date_range = (
        " - ".join(value for value in (source.start, source.end) if value) or None
    )
    return ResumeSection(
        section_name="Experience" if source.category == "experience" else "Projects",
        item_title=source.title,
        organization=source.organization,
        location=source.location,
        date_range=date_range,
        url=source.url,
        bullets=[ResumeBullet(text=source.bullets[0], source_item_id=source.id)],
        layout="compact",
    )


def _validate_content(
    content: ResumeContent,
    profile: RetrievedProfile,
    allowed_ids: "set[str] | list[str]",
    featured_ids: "set[str] | list[str] | None" = None,
    required_ids: "set[str] | list[str] | None" = None,
) -> ResumeContent:
    """Validate and normalize generated content against the profile.

    ``allowed_ids`` bounds which source items the resume may cite. Section
    layout (full vs compact) is taken from ``featured_ids`` when provided
    (deterministic tiering, used by the first write), otherwise from each
    section's own ``layout`` (model-assigned, used when revising).
    """
    sources = {item.id: item for item in profile.items}
    allowed = set(allowed_ids)
    featured = set(featured_ids) if featured_ids is not None else None
    allowed_skills = {
        skill.lower()
        for values in profile.skills.values()
        for skill in values
    }
    unsupported_skills = {
        skill for skill in content.skills if skill.lower() not in allowed_skills
    }
    if unsupported_skills:
        raise ValueError(f"Resume contains unsupported skills: {unsupported_skills}")

    # Group bullets by source item so each item renders as a single section.
    # Each input section must cite exactly one allowed source; multiple sections
    # citing the same source are merged (preserving first-seen order).
    grouped: "OrderedDict[str, dict]" = OrderedDict()
    for section in content.sections:
        source_ids = {bullet.source_item_id for bullet in section.bullets}
        if len(source_ids) != 1:
            raise ValueError("Each resume section must reference exactly one source item")
        source_id = next(iter(source_ids))
        if source_id not in allowed:
            raise ValueError(f"Resume cites an unselected source ID: {source_id}")
        entry = grouped.setdefault(source_id, {"bullets": [], "layout": section.layout})
        entry["bullets"].extend(section.bullets)

    def is_featured(source_id: str, model_layout: str) -> bool:
        if featured is not None:
            return source_id in featured
        return model_layout == "full"

    normalized_sections = []
    for source_id, entry in grouped.items():
        source = sources[source_id]
        date_range = (
            " - ".join(value for value in (source.start, source.end) if value)
            or None
        )
        # Featured items keep their full bullet set; compact items are
        # one-liners (keep only the strongest bullet).
        full = is_featured(source_id, entry["layout"])
        normalized_sections.append(
            ResumeSection(
                section_name=(
                    "Experience" if source.category == "experience" else "Projects"
                ),
                item_title=source.title,
                organization=source.organization,
                location=source.location,
                date_range=date_range,
                url=source.url,
                bullets=entry["bullets"] if full else entry["bullets"][:1],
                layout="full" if full else "compact",
            )
        )

    # Guarantee required (pinned) items appear, even if the model omitted them:
    # inject a deterministic compact line built from the item's own first fact.
    present = {b.source_item_id for s in normalized_sections for b in s.bullets}
    for required_id in required_ids or []:
        if required_id not in present and sources[required_id].bullets:
            normalized_sections.append(_compact_section_for(sources[required_id]))

    # A resume needs at least one full item; promote the first if none qualified.
    if normalized_sections and not any(s.layout == "full" for s in normalized_sections):
        normalized_sections[0] = normalized_sections[0].model_copy(
            update={"layout": "full"}
        )
    return content.model_copy(update={"sections": normalized_sections})


def _assemble(content: ResumeContent, profile: RetrievedProfile) -> ResumeDraft:
    contact = profile.candidate.contact
    return ResumeDraft(
        name=contact.name,
        email=contact.email,
        phone=contact.phone,
        location=contact.location,
        links=contact.links,
        headline=content.headline,
        summary=content.summary,
        education=profile.candidate.education,
        skills=content.skills,
        sections=content.sections,
        achievements=profile.candidate.achievements[:2],
    )


def emphasis_clause(emphasis: str) -> str:
    """Instruction fragment that steers the headline/summary toward an angle."""
    if not emphasis.strip():
        return ""
    return (
        " Lead the headline and summary with this angle, and prefer bullets that "
        f"evidence it: {emphasis.strip()}"
    )


def write_resume(
    job: JobAnalysis,
    plan: ResumePlan,
    profile: RetrievedProfile,
    emphasis: str = "",
    pinned_ids: "list[str] | None" = None,
) -> ResumeDraft:
    selected = [
        item for item in profile.items if item.id in set(plan.selected_item_ids)
    ]
    content = ask_structured(
        instructions=(
            "Write a tailored resume from the supplied plan and source items that "
            "fills a single US Letter page without overflowing. Use concise "
            "action-oriented bullets. Preserve every metric and claim exactly in "
            "meaning; do not add facts. Each bullet must cite its source_item_id. "
            "Set section_name to Experience or Projects and item_title to the "
            "source role or project name. Items in FEATURED_ITEM_IDS get two or "
            "three bullets each; items in ADDITIONAL_ITEM_IDS get exactly one "
            "concise bullet capturing their single strongest achievement. For the "
            "skills list, choose only from the supplied skills and copy each one "
            "verbatim — exact spelling and punctuation; do not rename, split, "
            "merge, abbreviate, or add skills. Keep the summary to at most two "
            "sentences, keep each bullet to roughly one line (about 130 characters "
            "or fewer), and keep bullets focused on the work itself — never put "
            "education, GPA, or coursework in an experience or project item."
            + emphasis_clause(emphasis)
        ),
        input_text=(
            f"JOB:\n{job.model_dump_json(indent=2)}\n\n"
            f"FEATURED_ITEM_IDS: {plan.featured_item_ids}\n"
            f"ADDITIONAL_ITEM_IDS: {plan.additional_item_ids}\n\n"
            f"PLAN:\n{plan.model_dump_json(indent=2)}\n\n"
            f"SELECTED SOURCES:\n"
            f"{RetrievedProfile(candidate=profile.candidate, items=selected, skills=profile.skills).model_dump_json(indent=2)}"
        ),
        schema=ResumeContent,
    )
    content = _validate_content(
        content,
        profile,
        allowed_ids=plan.selected_item_ids,
        featured_ids=plan.featured_item_ids,
        required_ids=pinned_ids,
    )
    return _assemble(content, profile)
