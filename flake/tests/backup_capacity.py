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
gib = 1024**3
before = dict(old, available_bytes=800 * gib)
recovered = dict(old, epoch=86400, available_bytes=1000 * gib)
after = dict(current, epoch=3 * 86400, available_bytes=900 * gib)
assert trend([before, recovered], after)["net_bytes_per_day"] == 50 * gib
assert trend([before], recovered)["after_large_reclamation"]
print("capacity growth, cleanup, destination identity and minimum history passed")
alert = runpy.run_path(sys.argv[1])["alert"]
day = 86400
# 557 GiB free shrinking by 10.3 GiB a day: 54 days left, no alert.
plenty = trend(
    [dict(old, epoch=0, available_bytes=round((557 + 8 * 10.3) * gib))],
    dict(current, epoch=8 * day, available_bytes=557 * gib),
)
assert 53 < plenty["days_remaining"] < 55
assert not alert(plenty)
# 250 GiB free shrinking by 10 GiB a day: 25 days left, alert.
short = trend(
    [dict(old, epoch=0, available_bytes=330 * gib)],
    dict(current, epoch=8 * day, available_bytes=250 * gib),
)
assert short["days_remaining"] == 25
assert alert(short)
assert not alert(trend([dict(old, epoch=86401)], current))
print("capacity alerts on projected days remaining, not free bytes")
