"""Output-style rules applied to every LLM call (see `call_structured`).

Product rule: text shown to users must not contain em dashes. We enforce it twice:
the rule is appended to every system prompt, and a scrubber rewrites any em dash that
still slips into the structured output before it is validated or stored.
"""

from __future__ import annotations

import re
from typing import Any

EM_DASH = "—"

STYLE_RULES = (
    "\n\nOUTPUT STYLE (applies to every string you write, in every field):\n"
    f"- Never use the em dash character ({EM_DASH}). Use a comma, colon, period or parentheses instead, "
    "or split the thought into two sentences.\n"
    "- If you quote a source that contains one, replace it with a comma inside the quote.\n"
    "- Write plainly, in complete sentences a non-expert can follow."
)

_EM_DASH_RE = re.compile(rf"\s*{EM_DASH}\s*")


def scrub_em_dashes(value: Any) -> Any:
    """Recursively replace em dashes in strings with a comma (safety net behind the prompt rule)."""
    if isinstance(value, str):
        if EM_DASH not in value:
            return value
        cleaned = _EM_DASH_RE.sub(", ", value)
        # A dash at the very start or end would leave a dangling comma.
        return cleaned.strip(", ") if value.lstrip().startswith(EM_DASH) or value.rstrip().endswith(EM_DASH) else cleaned
    if isinstance(value, list):
        return [scrub_em_dashes(v) for v in value]
    if isinstance(value, dict):
        return {k: scrub_em_dashes(v) for k, v in value.items()}
    return value
