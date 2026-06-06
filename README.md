# Resume Generator

Resume Generator is an early step toward making job applications less about
resume optimization and more about the work that makes someone a strong
candidate: learning, building experience, completing projects, developing a
craft, and pursuing genuine interests.

Most people accumulate useful evidence of their abilities across many places
and formats, then have to repeatedly translate it into the language of each job
description. This project aims to make that translation easier. Given a
candidate's factual experience data and either a job description or target
role, it selects relevant material and produces a tailored, one-page resume.

The goal is not to invent a better version of a candidate. It is to help people
present the experience they actually have, with less repetitive formatting and
keyword work.

## Vision

The longer-term system will provide multiple ways for people to continuously
record their experiences, projects, interests, skills, accomplishments, and
learning. Those inputs may be structured forms, notes, documents, messages, or
other unstructured data.

That personal experience record can then become a useful, queryable source of
truth. People should be able to:

- add or update experience data using natural language;
- send unstructured material and have it organized into reviewable records;
- ask questions about their own work, skills, and history;
- compare their evidence with a job description or target role; and
- generate truthful, tailored resumes for specific opportunities.

Resume generation is the first output channel, not the final shape of the
project. Over time, the system should reduce the administrative burden of
applying for work while keeping the person's real experience at the center.

## V1

V1 is deliberately small: a command-line resume-tailoring pipeline built with
plain Python, the Anthropic Messages API, Pydantic Structured Outputs, JSON
profile data, Jinja2, and WeasyPrint.

Candidate records are currently maintained in curated JSON files. The natural
language ingestion, ongoing experience capture, and general querying described
above are future directions, not current V1 features.

```text
Job description OR target role
  -> analyze job / expand role
  -> retrieve relevant profile items
  -> plan resume (featured + additional tiers)
  -> write resume
  -> critique + revise loop (until a well-filled single page, max 3 rounds)
  -> render PDF
```

The application owns the workflow directly. There is no LangChain, LangGraph,
Agents SDK, vector database, or UI in V1.

## Structure

```text
app/
  main.py
  config.py
  models.py
  llm.py
  pipeline/
    analyze_job.py
    retrieve_profile.py
    plan_resume.py
    write_resume.py
    refine.py
    render_pdf.py
  data/
    profile.json
    projects.json
    experiences.json
    skills.json
    roles.json
  templates/
    resume.html
    resume.css
  output/
```

## Setup

Requires Python 3.9 or newer.

WeasyPrint requires its native system dependencies. Follow the
[WeasyPrint installation guide](https://doc.courtbouillon.org/weasyprint/stable/first_steps.html#installation)
for your platform if `pip install` or PDF rendering fails.

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
```

Set `ANTHROPIC_API_KEY` in `.env`. The default model is `claude-opus-4-8`;
override it with `ANTHROPIC_MODEL`.

## Run

Tailor to a full job description:

```bash
python -m app.main --job job_description.txt
```

Or tailor to a target role/title (no posting needed):

```bash
python -m app.main --role "AI Engineer"
python -m app.main --role "Backend Engineer"
python -m app.main --role "Data Scientist"
```

`--job` and `--role` are mutually exclusive; exactly one is required.

When `--role` matches a curated preset in `app/data/roles.json` (case- and
whitespace-insensitive, with aliases), targeting is loaded **deterministically**
from that file — no LLM call. Currently curated: AI Engineer, Backend Engineer,
Data Scientist, Machine Learning Engineer, Full Stack Engineer, Software
Engineer, and Quantitative Researcher. An unrecognized role falls back to an
LLM that expands the title into typical targeting criteria. Add or edit presets
by editing `roles.json`.

Optional output path (works with either input):

```bash
python -m app.main --role "AI Engineer" --output app/output/ai_resume.pdf
```

### Controlling content

Two optional flags steer selection and angle:

- `--include` forces specific profile items into the resume, by item ID or a
  case-insensitive title substring (comma-separated). Pinned items are
  guaranteed to appear (as a compact line if the planner wouldn't otherwise pick
  them).
- `--emphasis` is a free-text angle the headline and summary lead with, and that
  selection is biased toward.

```bash
python -m app.main --role "AI Engineer" \
  --include "hsp,eth-momentum" \
  --emphasis "shipped production systems used by real paying customers"
```

The final HTML, PDF, and intermediate JSON artifacts are written to the output
directory.

Planning splits items into a **featured** tier (full entries with two or three
bullets) and an **additional** tier (compact one-line entries) to fill the page
with breadth rather than whitespace. After writing, a bounded critique→revise
loop measures how the draft fills the page (`render_pdf` reports page count and a
fill ratio) and revises up to `MAX_REFINE_ITERATIONS` times (default 3): it
trims when the content overflows and expands when the page underfills, then keeps
the best-fitting draft. The renderer still rejects a final resume that exceeds one
page. Tunable via `MAX_REFINE_ITERATIONS`, `FILL_TARGET_MIN`, `FILL_TARGET_MAX`.

Structured Outputs follow Anthropic's current guidance:
[Structured outputs](https://platform.claude.com/docs/en/build-with-claude/structured-outputs).
