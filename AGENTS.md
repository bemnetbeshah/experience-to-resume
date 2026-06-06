# Resume Generator V1

## Scope

- Use plain Python, the Anthropic Messages API, JSON source files, Jinja2, and WeasyPrint.
- Do not add LangChain, LangGraph, the Agents SDK, vector databases, or a UI in V1.
- Keep orchestration explicit in `app/main.py`.

## Pipeline

`job description OR target role -> analyze/expand -> retrieve -> plan -> write -> (critique -> revise)* -> render`

- Input is either a full job description (`--job <file>`) or a target role/title
  (`--role "<title>"`); the two are mutually exclusive and exactly one is required.
- A `--role` is first matched against deterministic, curated presets in
  `app/data/roles.json`; an unmatched role falls back to an LLM that expands the
  title into `JobAnalysis` criteria. Either path yields a validated `JobAnalysis`,
  so downstream stages are unchanged.
- LLM stages must return Pydantic-validated Structured Outputs.
- Retrieval and rendering must remain deterministic.
- Candidate facts must come from `app/data/*.json`; never invent employers, dates, metrics, education, contact details, or skills.
- Preserve source IDs through planning so generated claims can be traced to profile records.
- Planning tiers items into `featured_item_ids` (full, 2–3 bullets) and
  `additional_item_ids` (compact one-liners) to fill the page without bloat.
- Aim to fill a single US Letter page. `render_pdf` measures page count and a
  fill ratio; `main.py` runs a bounded critique→revise loop
  (`MAX_REFINE_ITERATIONS`, default 3) that trims when content overflows and
  expands when the page underfills, then keeps the best-fitting draft. The final
  `render_pdf` still fails clearly if the chosen draft exceeds one page.
- Keep the refine loop an explicit Python loop in `main.py` — no Agents SDK.

## Commands

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
python -m app.main --job job_description.txt
python -m app.main --role "AI Engineer"
python -m app.main --role "AI Engineer" --include "hsp,eth-momentum" --emphasis "shipped production systems used by paying customers"
```

`--include` (item IDs or title substrings) force-includes items; `--emphasis`
steers the headline/summary angle. Both are optional and reusable across inputs.

## Verification

```bash
python -m compileall app
python -m app.main --help
```

Do not commit `.env`, API keys, generated files in `app/output/`, or local virtual environments.
