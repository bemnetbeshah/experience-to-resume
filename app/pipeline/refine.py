"""Critique a draft and revise it toward a well-filled, grounded single page."""

from __future__ import annotations

from app.config import FILL_TARGET_MAX, FILL_TARGET_MIN
from app.llm import ask_structured
from app.models import (
    JobAnalysis,
    ResumeContent,
    ResumeCritique,
    ResumeDraft,
    RetrievedProfile,
)
from app.pipeline.render_pdf import FitMetrics
from app.pipeline.write_resume import _assemble, _validate_content, emphasis_clause


def critique_resume(
    job: JobAnalysis,
    draft: ResumeDraft,
    profile: RetrievedProfile,
    metrics: FitMetrics,
) -> ResumeCritique:
    return ask_structured(
        instructions=(
            "You are a strict resume reviewer. Judge the resume for relevance to "
            "the job, concision, grounding (every claim must be supported by the "
            "supplied profile), and page fit. The fit metrics report how the draft "
            f"lays out: a single well-filled page has page_count == 1 and "
            f"fill_ratio between {FILL_TARGET_MIN} and {FILL_TARGET_MAX}. Set "
            "satisfied=true only when it is a single, well-filled page with no "
            "relevance or grounding problems. Set fit_action to 'trim' if it "
            "overflows one page or is too dense, 'expand' if it underfills the "
            "page (leaves whitespace), or 'ok' if the fill is good. List concrete "
            "issues and actionable suggestions tied to the supplied profile."
        ),
        input_text=(
            f"JOB:\n{job.model_dump_json(indent=2)}\n\n"
            f"FIT METRICS: page_count={metrics.page_count}, "
            f"fill_ratio={metrics.fill_ratio:.3f} "
            f"(target {FILL_TARGET_MIN}-{FILL_TARGET_MAX})\n\n"
            f"PROFILE (allowed facts):\n{profile.model_dump_json(indent=2)}\n\n"
            f"DRAFT:\n{draft.model_dump_json(indent=2)}"
        ),
        schema=ResumeCritique,
    )


def _fit_directive(metrics: FitMetrics) -> str:
    if metrics.page_count > 1:
        return (
            f"The resume currently overflows to {metrics.page_count} pages. TRIM to "
            "one page: tighten wording, drop the weakest bullets, and move marginal "
            "items to a single compact line (layout='compact')."
        )
    if metrics.fill_ratio < FILL_TARGET_MIN:
        pct = round(metrics.fill_ratio * 100)
        return (
            f"The resume only fills about {pct}% of the page, leaving whitespace. "
            "EXPAND using only supplied facts: add more relevant profile items as "
            "compact one-liners (layout='compact'), promote a strong compact item "
            "to full (layout='full') with two or three bullets, or add one more "
            "strong bullet to a featured item."
        )
    return "Page fit is good; focus on polish, relevance, and the critique below."


def revise_resume(
    job: JobAnalysis,
    draft: ResumeDraft,
    profile: RetrievedProfile,
    critique: ResumeCritique,
    metrics: FitMetrics,
    emphasis: str = "",
    pinned_ids: "list[str] | None" = None,
) -> ResumeDraft:
    allowed_ids = [item.id for item in profile.items]
    pinned_ids = pinned_ids or []
    pin_note = (
        f" Always keep these item IDs present in the resume: {pinned_ids}."
        if pinned_ids
        else ""
    )
    content = ask_structured(
        instructions=(
            "Revise the resume to address the critique and the fit directive while "
            "staying grounded in the supplied profile. Each bullet must cite its "
            "source_item_id, drawn only from the supplied profile items. Mark each "
            "section's layout as 'full' (two or three bullets, for the most "
            "important items) or 'compact' (exactly one bullet, for breadth); keep "
            "at least three 'full' items. Set section_name to Experience or "
            "Projects and item_title to the source role or project name. For the "
            "skills list, choose only from the supplied skills and copy each "
            "verbatim — do not rename, split, merge, abbreviate, or add skills. "
            "Keep the summary to at most two sentences, each bullet to about one "
            "line, and never put education, GPA, or coursework in an experience or "
            "project item." + pin_note + emphasis_clause(emphasis)
        ),
        input_text=(
            f"JOB:\n{job.model_dump_json(indent=2)}\n\n"
            f"FIT DIRECTIVE: {_fit_directive(metrics)}\n\n"
            f"CRITIQUE:\n{critique.model_dump_json(indent=2)}\n\n"
            f"PROFILE (allowed facts and item IDs):\n"
            f"{profile.model_dump_json(indent=2)}\n\n"
            f"CURRENT DRAFT:\n{draft.model_dump_json(indent=2)}"
        ),
        schema=ResumeContent,
    )
    content = _validate_content(
        content, profile, allowed_ids=allowed_ids, required_ids=pinned_ids
    )
    return _assemble(content, profile)
