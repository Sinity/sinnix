"""sinnix-sentinel Python port (observe-only by default).

This package mirrors the bash script at scripts/sinnix-sentinel byte-for-byte
on its on-disk JSON formats. The Python implementation ships with
``--observe-only`` enabled by default; corrective and notification side
effects are wire-compatible but gated on explicit flags so the live bash
sentinel and this Python port can run side-by-side during validation.
"""

__all__ = ["__version__"]
__version__ = "0.1.0"
