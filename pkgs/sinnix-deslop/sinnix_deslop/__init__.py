"""sinnix-deslop: regex-based LLM-slop phrase stripping (sinnix-uou).

Output cleanup, never a generation-time gate (no-prose-grepping-for-
ENFORCEMENT: this filters cosmetic prose after the fact, it does not police
generation). Phrase list lives in phrases.txt as versioned data, not code.
"""

from .filter import Rule, deslop, load_rules

__all__ = ["Rule", "deslop", "load_rules"]
