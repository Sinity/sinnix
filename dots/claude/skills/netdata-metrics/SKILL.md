---
description: Query netdata API for real-time system metrics analysis. Use when investigating CPU spikes, memory pressure, disk I/O, network activity, or any system performance questions.
allowed-tools: Bash(curl:*), Bash(python*:*), Read, Write
argument-hint: [chart-name|"summary"|"diagnose"] [time-range-seconds]
---

# Netdata System Metrics Analyzer

Query the local netdata instance at `http://localhost:19999` for comprehensive system metrics.

## Quick Commands

```bash
# CPU usage last 5 minutes
curl -s "http://localhost:19999/api/v1/data?chart=system.cpu&after=-300&format=json"

# Memory usage
curl -s "http://localhost:19999/api/v1/data?chart=system.ram&after=-300&format=json"

# Disk I/O (all disks)
curl -s "http://localhost:19999/api/v1/data?chart=system.io&after=-300&format=json"

# Network traffic
curl -s "http://localhost:19999/api/v1/data?chart=system.net&after=-300&format=json"

# List all 2000+ available charts
curl -s "http://localhost:19999/api/v1/charts" | jq '.charts | keys'

# Per-process CPU (apps plugin)
curl -s "http://localhost:19999/api/v1/data?chart=apps.cpu&after=-300&format=json"
```

## Analysis Script

For deeper analysis, use the Python script:

```bash
# Summary of current system state
python ~/.claude/skills/netdata-metrics/scripts/analyze.py summary

# Diagnose performance issues
python ~/.claude/skills/netdata-metrics/scripts/analyze.py diagnose

# Specific chart analysis
python ~/.claude/skills/netdata-metrics/scripts/analyze.py chart system.cpu 3600

# Export to CSV for lynchpin
python ~/.claude/skills/netdata-metrics/scripts/analyze.py export system.cpu 86400 > /tmp/cpu_24h.csv
```

## Key Charts

| Chart | Description |
|-------|-------------|
| `system.cpu` | Overall CPU by type (user, system, iowait, etc.) |
| `system.ram` | Memory usage (used, cached, buffers, free) |
| `system.io` | Disk I/O operations |
| `system.net` | Network bytes in/out |
| `system.load` | System load averages |
| `apps.cpu` | Per-application CPU usage |
| `apps.mem` | Per-application memory |
| `disk_space.*` | Disk space per mount |
| `cgroup_*` | Container/systemd service metrics |

## API Parameters

- `chart` - Chart name (required)
- `after` - Start time, negative = seconds ago (e.g., `-3600` = last hour)
- `before` - End time (default: now)
- `points` - Number of data points to return
- `group` - Aggregation: `average`, `sum`, `min`, `max`
- `format` - Output: `json`, `csv`, `prometheus`
- `options` - Modifiers: `objectrows`, `nonzero`, `abs`, `null2zero`

See [reference.md](reference.md) for complete API documentation.

## Usage Patterns

**Investigating a CPU spike:**
```bash
# Get CPU data around the time of interest
curl -s "http://localhost:19999/api/v1/data?chart=system.cpu&after=-1800&points=100&format=json&options=objectrows" | jq '.data | sort_by(.user) | reverse | .[0:5]'

# Check which processes were using CPU
curl -s "http://localhost:19999/api/v1/data?chart=apps.cpu&after=-1800&format=json"
```

**Memory pressure analysis:**
```bash
# Memory over last hour
curl -s "http://localhost:19999/api/v1/data?chart=system.ram&after=-3600&points=60" | jq '.data | .[] | {time: .[0], used_gb: (.[2]/1024)}'
```

**Disk I/O bottleneck:**
```bash
# I/O wait correlation with disk activity
curl -s "http://localhost:19999/api/v1/data?chart=system.io&after=-600&format=json"
curl -s "http://localhost:19999/api/v1/data?chart=system.cpu&after=-600&dimensions=iowait&format=json"
```
