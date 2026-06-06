"""Thin Anthropic Messages API wrapper with Pydantic Structured Outputs."""

from __future__ import annotations

from typing import TypeVar

import anthropic
from pydantic import BaseModel

from app.config import ANTHROPIC_MODEL, MAX_TOKENS


StructuredModel = TypeVar("StructuredModel", bound=BaseModel)


def ask_structured(
    instructions: str,
    input_text: str,
    schema: type[StructuredModel],
) -> StructuredModel:
    client = anthropic.Anthropic()
    response = client.messages.parse(
        model=ANTHROPIC_MODEL,
        max_tokens=MAX_TOKENS,
        system=instructions,
        messages=[{"role": "user", "content": input_text}],
        output_format=schema,
    )
    if response.parsed_output is None:
        raise RuntimeError("Claude returned no parsed structured output")
    return response.parsed_output
