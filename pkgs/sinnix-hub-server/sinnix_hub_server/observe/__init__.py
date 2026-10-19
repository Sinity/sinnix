"""Agent-readable workstation observability report.

The command intentionally keeps machine-specific joining in Sinnix while
reading project-native ledgers from Sinex and Polylogue. Project ledgers do not
yet expose every field we need, so rows carry explicit gap codes instead of
pretending the join is complete.
"""

from __future__ import annotations

SCHEMA = "sinnix-observe-v1"
