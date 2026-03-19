---
name: lynchpin-life-timeline
description: Build monthly life timeline aggregates from personal telemetry (Takeout, finance, health, git, Reddit, Wykop, Spotify, webhistory)
user_invocable: true
---

# lynchpin-life-timeline

Build monthly "life timeline" metrics from local personal telemetry sources via
the reusable `lynchpin.retrospective.run_life_timeline(...)` API, with
`lynchpin.system.life_timeline*` kept as thin CLI wrappers for concrete
artefact writes.

## Latest Refresh Sequence

There is no `just life-refresh` wrapper surface anymore. Compose the modules in
this order from `/realm/project/sinity-lynchpin`.

1. Build the latest JSON timeline plus drilldowns.

```bash
END="$(date +%Y-%m)"

python -m lynchpin.system.life_timeline \
  --start 2013-10 \
  --end "$END" \
  --output artefacts/lifelog/life-timeline/monthly_life_latest.json \
  --markdown-output-dir artefacts/lifelog/life-timeline/life_drilldowns_latest
```

2. Optionally enrich the YouTube oEmbed cache.

```bash
python -m lynchpin.system.life_timeline_oembed enrich \
  --life-json artefacts/lifelog/life-timeline/monthly_life_latest.json \
  --cache artefacts/lifelog/life-timeline/youtube_oembed_cache.jsonl \
  --start 2013-10 \
  --end "$END"
```

If you need newly fetched titles or channels reflected in
`monthly_life_latest.json`, rerun step 1 after enrichment.

3. Render the digest from the timeline JSON.

```bash
python -m lynchpin.system.life_timeline_digest \
  --life-json artefacts/lifelog/life-timeline/monthly_life_latest.json \
  --output artefacts/lifelog/life-timeline/digests/life_earliest_to_now.monthly.md
```

4. Render the quarterly and yearly narrative.

```bash
python -m lynchpin.system.life_timeline_narrative \
  --life-json artefacts/lifelog/life-timeline/monthly_life_latest.json \
  --output artefacts/lifelog/life-timeline/narratives/life_auto_summary.md
```

## Fixed-Range Build

```bash
python -m lynchpin.system.life_timeline \
  --start 2020-04 \
  --end 2023-04 \
  --output artefacts/lifelog/life-timeline/monthly_life_2020-04_to_2023-04.json \
  --markdown-output artefacts/lifelog/life-timeline/life_2020-04_to_2023-04.generated.md
```

Use `--markdown-output` for a single Markdown drilldown or
`--markdown-output-dir` for per-year drilldowns.

## Range Arguments

All timeline commands accept `--start YYYY-MM` and `--end YYYY-MM`. Module
defaults are `2020-04` to `2023-04`; latest refreshes should pass explicit
bounds.

## Cache Files

- `artefacts/lifelog/life-timeline/youtube_oembed_cache.jsonl` — oEmbed response cache
- `artefacts/lifelog/life-timeline/monthly_life_latest.json` — latest JSON timeline

## Output Directory

`artefacts/lifelog/life-timeline/`

## Data Sources

Reddit, Wykop, webhistory, Raindrop bookmarks, Goodreads, Spotify, finance (hledger), Samsung Health (sleep + weight), Dendron notes, git activity, Google Takeout (Search, YouTube, Chrome, Location, Play Store, Maps).

## API

```python
from pathlib import Path
from lynchpin.retrospective import LifeTimelineInputs, LifeTimelineResult, run_life_timeline
result: LifeTimelineResult = run_life_timeline(
    start_month="2024-01",
    end_month="2024-12",
    output=Path("..."),
    inputs=LifeTimelineInputs(),
)
```
