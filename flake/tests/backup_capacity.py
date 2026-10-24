"""Discriminate exhaustion, cleanup, new destinations and insufficient history."""

import runpy
import sys

trend = runpy.run_path(sys.argv[1])["trend"]
old = {"filesystem_uuid": "synthetic-a", "epoch": 0, "available_bytes": 1000}
current = {"filesystem_uuid": "synthetic-a", "epoch": 2 * 86400, "available_bytes": 800}
result = trend([old], current)
assert result["net_bytes_per_day"] == 100
assert result["days_remaining"] == 8
assert (
    trend([dict(old, filesystem_uuid="synthetic-b")], current)["status"]
    == "insufficient_history"
)
assert trend([dict(old, epoch=86401)], current)["status"] == "insufficient_history"
assert trend([dict(old, available_bytes=700)], current)["days_remaining"] is None
print("capacity growth, cleanup, destination identity and minimum history passed")
