"""Render a validated resume to HTML and a single-page PDF, with fit metrics."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from jinja2 import Environment, FileSystemLoader, StrictUndefined, select_autoescape

from app.config import OUTPUT_DIR, TEMPLATE_DIR
from app.models import ResumeDraft


@dataclass(frozen=True)
class FitMetrics:
    """How well a rendered draft fills the page."""

    page_count: int
    fill_ratio: float  # content height / usable page height on page 1 (0..1)


def _environment() -> Environment:
    return Environment(
        loader=FileSystemLoader(TEMPLATE_DIR),
        undefined=StrictUndefined,
        autoescape=select_autoescape(("html", "xml")),
    )


def _build_document(resume: ResumeDraft):
    """Render the template and lay it out with WeasyPrint. Returns (html, document)."""
    try:
        from weasyprint import CSS, HTML
    except OSError as exc:
        raise RuntimeError(
            "WeasyPrint native libraries are missing. Follow the installation "
            "guide linked in README.md."
        ) from exc

    html = _environment().get_template("resume.html").render(resume=resume)
    document = HTML(string=html, base_url=str(TEMPLATE_DIR)).render(
        stylesheets=[CSS(filename=TEMPLATE_DIR / "resume.css")]
    )
    return html, document


def _content_bottom(box) -> float:
    """Absolute Y of the lowest edge of a box and its descendants."""
    position_y = getattr(box, "position_y", None)
    if position_y is None:
        return 0.0
    if hasattr(box, "margin_height"):
        bottom = position_y + box.margin_height()
    else:
        bottom = position_y + (getattr(box, "height", 0) or 0)
    for child in getattr(box, "children", ()) or ():
        bottom = max(bottom, _content_bottom(child))
    return bottom


def _measure(document) -> FitMetrics:
    pages = document.pages
    page = pages[0]
    page_box = page._page_box
    try:
        margin_top = getattr(page_box, "margin_top", 0) or 0
        margin_bottom = getattr(page_box, "margin_bottom", 0) or 0
        usable = page.height - margin_top - margin_bottom
        # Measure only the content children, not the full-height page box itself.
        bottom = max(
            (_content_bottom(child) for child in (page_box.children or ())),
            default=margin_top,
        )
        content_height = max(0.0, bottom - margin_top)
        fill_ratio = content_height / usable if usable > 0 else 0.0
    except Exception:
        # Layout-tree introspection is best-effort; fall back conservatively.
        fill_ratio = 0.9 if len(pages) == 1 else 1.0
    return FitMetrics(page_count=len(pages), fill_ratio=min(fill_ratio, 1.0))


def evaluate_fit(resume: ResumeDraft) -> FitMetrics:
    """Lay out the draft without writing files and report how it fits the page."""
    _html, document = _build_document(resume)
    return _measure(document)


def render_pdf(
    resume: ResumeDraft,
    output_path: Path | None = None,
) -> Path:
    output_path = (output_path or OUTPUT_DIR / "resume.pdf").resolve()
    output_path.parent.mkdir(parents=True, exist_ok=True)

    html, document = _build_document(resume)
    html_path = output_path.with_suffix(".html")
    html_path.write_text(html, encoding="utf-8")

    metrics = _measure(document)
    if metrics.page_count != 1:
        raise RuntimeError(
            f"Resume must fit one page; rendered {metrics.page_count} pages"
        )
    document.write_pdf(output_path)
    return output_path
