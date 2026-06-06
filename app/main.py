"""Command-line entry point for the explicit V1 resume pipeline."""

from __future__ import annotations

import argparse
from pathlib import Path

from app.config import (
    FILL_TARGET_MAX,
    FILL_TARGET_MIN,
    MAX_REFINE_ITERATIONS,
    OUTPUT_DIR,
)
from app.models import JobAnalysis
from app.pipeline.analyze_job import analyze_job, analyze_role, load_role_preset
from app.pipeline.plan_resume import plan_resume
from app.pipeline.refine import critique_resume, revise_resume
from app.pipeline.render_pdf import FitMetrics, evaluate_fit, render_pdf
from app.pipeline.retrieve_profile import load_profile, retrieve_profile
from app.pipeline.write_resume import write_resume


def _well_filled(metrics: FitMetrics) -> bool:
    return (
        metrics.page_count == 1
        and FILL_TARGET_MIN <= metrics.fill_ratio <= FILL_TARGET_MAX
    )


def _fit_score(metrics: FitMetrics) -> float:
    """Higher is better. Single-page drafts always beat multi-page ones."""
    if metrics.page_count != 1:
        return -float(metrics.page_count)
    if metrics.fill_ratio > FILL_TARGET_MAX:
        # On one page but slightly over the band: prefer closer to the band.
        return 1.0 - (metrics.fill_ratio - FILL_TARGET_MAX)
    return metrics.fill_ratio


def _resolve_includes(tokens: list[str]) -> list[str]:
    """Resolve --include tokens (item IDs or title substrings) to profile IDs."""
    items = load_profile().items
    resolved: list[str] = []
    for raw in tokens:
        token = raw.strip().lower()
        if not token:
            continue
        matches = [
            item.id
            for item in items
            if token in item.id.lower() or token in item.title.lower()
        ]
        if not matches:
            raise SystemExit(f"--include: no profile item matches '{raw}'")
        resolved.extend(matches)
    # De-duplicate while preserving order.
    seen: set[str] = set()
    return [i for i in resolved if not (i in seen or seen.add(i))]


def generate_resume(
    job: JobAnalysis,
    output_path: Path | None = None,
    include_ids: list[str] | None = None,
    emphasis: str = "",
) -> Path:
    include_ids = include_ids or []
    profile = retrieve_profile(job)

    # Make sure pinned items are available to planning even if ranked outside
    # the retrieval window.
    if include_ids:
        present = {item.id for item in profile.items}
        extra = [
            item
            for item in load_profile().items
            if item.id in set(include_ids) and item.id not in present
        ]
        if extra:
            profile = profile.model_copy(update={"items": [*profile.items, *extra]})

    plan = plan_resume(job, profile, pinned_ids=include_ids, emphasis=emphasis)

    draft = write_resume(
        job, plan, profile, emphasis=emphasis, pinned_ids=include_ids
    )
    metrics = evaluate_fit(draft)
    best_draft, best_metrics = draft, metrics
    print(
        f"Draft 0: {metrics.page_count} page(s), "
        f"fill {metrics.fill_ratio:.2f}"
    )

    for attempt in range(1, MAX_REFINE_ITERATIONS + 1):
        if _well_filled(metrics):
            break
        critique = critique_resume(job, draft, profile, metrics)
        if critique.satisfied and metrics.page_count == 1:
            break
        draft = revise_resume(
            job,
            draft,
            profile,
            critique,
            metrics,
            emphasis=emphasis,
            pinned_ids=include_ids,
        )
        metrics = evaluate_fit(draft)
        print(
            f"Revision {attempt} ({critique.fit_action}): "
            f"{metrics.page_count} page(s), fill {metrics.fill_ratio:.2f}"
        )
        if _fit_score(metrics) > _fit_score(best_metrics):
            best_draft, best_metrics = draft, metrics

    destination = output_path or OUTPUT_DIR / "resume.pdf"
    _write_artifacts(destination.parent, job, profile, plan, draft, best_draft)
    return render_pdf(best_draft, destination)


def _write_artifacts(output_dir: Path, *artifacts: object) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    names = ("job_analysis", "retrieved_profile", "resume_plan", "draft", "resume")
    if len(names) != len(artifacts):
        raise ValueError("Artifact name and value counts must match")
    for name, artifact in zip(names, artifacts):
        output_dir.joinpath(f"{name}.json").write_text(
            artifact.model_dump_json(indent=2),
            encoding="utf-8",
        )


def _arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Generate a tailored one-page resume PDF."
    )
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument(
        "--job",
        type=Path,
        help="Path to a plain-text job description.",
    )
    source.add_argument(
        "--role",
        type=str,
        help=(
            "A target job role/title to tailor toward, e.g. "
            "'AI Engineer', 'Backend Engineer', 'Data Scientist'."
        ),
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=OUTPUT_DIR / "resume.pdf",
        help="Destination PDF path.",
    )
    parser.add_argument(
        "--include",
        type=str,
        default="",
        help=(
            "Comma-separated profile item IDs or title substrings to force into "
            "the resume, e.g. 'hsp,eth-momentum'."
        ),
    )
    parser.add_argument(
        "--emphasis",
        type=str,
        default="",
        help=(
            "A free-text angle to lead the headline/summary with, e.g. "
            "'shipped production systems used by real paying customers'."
        ),
    )
    return parser.parse_args()


def main() -> int:
    args = _arguments()
    if args.job is not None:
        job = analyze_job(args.job.read_text(encoding="utf-8"))
    else:
        job = load_role_preset(args.role)
        if job is not None:
            print(f"Matched curated role preset: {job.role_title}")
        else:
            print(f"No preset for '{args.role}'; generating targeting criteria.")
            job = analyze_role(args.role)
    include_ids = _resolve_includes(args.include.split(",")) if args.include else []
    if include_ids:
        print(f"Forcing inclusion of: {include_ids}")
    path = generate_resume(job, args.output, include_ids=include_ids, emphasis=args.emphasis)
    print(f"Created resume: {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
