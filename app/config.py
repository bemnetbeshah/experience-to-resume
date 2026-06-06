"""Application configuration and stable project paths."""

from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv


ROOT_DIR = Path(__file__).resolve().parent.parent
APP_DIR = ROOT_DIR / "app"
DATA_DIR = APP_DIR / "data"
TEMPLATE_DIR = APP_DIR / "templates"
OUTPUT_DIR = APP_DIR / "output"

load_dotenv(ROOT_DIR / ".env")

ANTHROPIC_MODEL = os.getenv("ANTHROPIC_MODEL", "claude-opus-4-8")
MAX_TOKENS = int(os.getenv("ANTHROPIC_MAX_TOKENS", "8192"))

# Refinement loop: how many critique/revise rounds to attempt, and the target
# band for how full a single page should be (content height / usable height).
MAX_REFINE_ITERATIONS = int(os.getenv("MAX_REFINE_ITERATIONS", "3"))
FILL_TARGET_MIN = float(os.getenv("FILL_TARGET_MIN", "0.80"))
FILL_TARGET_MAX = float(os.getenv("FILL_TARGET_MAX", "0.98"))
