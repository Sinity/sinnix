"""Forecast from free space after each compaction, not from nightly swings."""

import runpy
import sys

script = runpy.run_path(sys.argv[1])
trend, alert = script["trend"], script["alert"]
gib = 1024**3
day = 86400


def week(start_day, after_compaction, nightly_drop, compacted):
    # Free space right after compaction, then a fall every night until the
    # next compaction returns it.
    return [
        {
            "filesystem_uuid": "synthetic-a",
            "epoch": (start_day + night) * day,
            "available_bytes": after_compaction - night * nightly_drop,
            "compacted_epoch": compacted,
        }
        for night in range(7)
    ]


# The live pattern: about 10 GiB a night returned weekly, flat between
# compactions. Nothing grows, so no forecast and no alert, although the
# nightly figures would project exhaustion within two months.
rows = (
    week(0, 661 * gib, 10 * gib, 0)
    + week(7, 663 * gib, 10 * gib, 7 * day)
    + week(14, 662 * gib, 10 * gib, 14 * day)
)
flat = trend(rows[:-1], rows[-1])
assert flat["status"] == "observed"
assert flat["cycle_drop_bytes"] == 60 * gib
assert flat["days_remaining"] is None or flat["days_remaining"] > 1000
assert not alert(flat, rows[-1]["available_bytes"])

# Real growth: post-compaction free space falls 70 GiB a week, 10 GiB a day.
growing = (
    week(0, 450 * gib, 10 * gib, 0)
    + week(7, 380 * gib, 10 * gib, 7 * day)
    + week(14, 310 * gib, 10 * gib, 14 * day)
)
forecast = trend(growing[:-1], growing[-1])
assert forecast["net_bytes_per_day"] == 10 * gib
assert forecast["days_remaining"] == 31
assert not alert(forecast, growing[-1]["available_bytes"])
shorter = growing[:14] + week(14, 250 * gib, 10 * gib, 14 * day)
assert alert(trend(shorter[:-1], shorter[-1]), shorter[-1]["available_bytes"])

# Less free space than one cycle consumes alerts before any forecast exists:
# the current cycle has fallen 60 GiB since compaction.
tight = week(0, 100 * gib, 10 * gib, 0)
early = trend(tight[:-1], tight[-1])
assert early["status"] == "insufficient_history"
assert early["cycle_drop_bytes"] == 60 * gib
assert alert(early, 40 * gib)
assert not alert(early, 61 * gib)

# Another destination starts a new history.
other = [dict(row, filesystem_uuid="synthetic-b") for row in rows[:-1]]
assert trend(other, rows[-1])["status"] == "insufficient_history"
print("capacity forecasts from post-compaction free space")
