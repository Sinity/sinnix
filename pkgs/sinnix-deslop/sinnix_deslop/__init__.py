"""sinnix-deslop: regex-based LLM-slop phrase stripping.

Output cleanup, never a generation-time gate: this filters cosmetic prose
after the fact, it does not police generation. The phrase list lives in
phrases.txt as versioned data, not code.
"""

from .filter import Rule, deslop, load_rules

__all__ = ["Rule", "deslop", "load_rules"]
