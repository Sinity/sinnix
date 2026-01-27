# Netdata API Reference

Base URL: `http://localhost:19999`

## Endpoints

### GET /api/v1/charts
List all available charts.

```bash
curl -s "http://localhost:19999/api/v1/charts" | jq '.charts | keys | length'
# Returns: 2358 (or similar)
```

Response structure:
```json
{
  "charts": {
    "system.cpu": {
      "id": "system.cpu",
      "name": "system.cpu",
      "type": "system",
      "family": "cpu",
      "units": "percentage",
      "update_every": 1,
      "dimensions": {
        "user": {"name": "user"},
        "system": {"name": "system"},
        "iowait": {"name": "iowait"}
      }
    }
  }
}
```

### GET /api/v1/data
Retrieve time-series data for a chart.

**Parameters:**

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `chart` | string | Yes | Chart ID (e.g., `system.cpu`) |
| `after` | int | No | Start time. Negative = seconds ago. Default: -600 |
| `before` | int | No | End time. Default: 0 (now) |
| `points` | int | No | Max data points to return |
| `group` | string | No | Aggregation: `average`, `sum`, `min`, `max`, `median` |
| `dimensions` | string | No | Comma-separated dimension filter |
| `format` | string | No | Output format: `json`, `csv`, `prometheus` |
| `options` | string | No | Comma-separated: `objectrows`, `nonzero`, `abs`, `null2zero`, `seconds`, `ms` |

**Examples:**

```bash
# Basic JSON (last 10 minutes)
curl -s "http://localhost:19999/api/v1/data?chart=system.cpu&after=-600"

# CSV format
curl -s "http://localhost:19999/api/v1/data?chart=system.cpu&after=-3600&format=csv"

# Object rows (easier to parse)
curl -s "http://localhost:19999/api/v1/data?chart=system.cpu&after=-60&format=json&options=objectrows"

# Specific dimensions only
curl -s "http://localhost:19999/api/v1/data?chart=system.cpu&dimensions=user,system&after=-300"

# Aggregated (1 point per minute over last hour)
curl -s "http://localhost:19999/api/v1/data?chart=system.cpu&after=-3600&points=60&group=average"
```

**Response (JSON):**
```json
{
  "labels": ["time", "user", "system", "nice", "iowait", "irq", "softirq", "steal", "guest", "guest_nice"],
  "data": [
    [1769174953, 15.35, 2.30, 0, 3.89, 0.17, 0.08, 0, 0, 0],
    [1769174952, 12.24, 2.51, 0.21, 3.68, 0.17, 0.08, 0, 0, 0]
  ]
}
```

**Response (objectrows):**
```json
{
  "labels": ["time", "user", "system"],
  "data": [
    {"time": 1769174953, "user": 15.35, "system": 2.30},
    {"time": 1769174952, "user": 12.24, "system": 2.51}
  ]
}
```

### GET /api/v1/info
Get netdata instance information.

```bash
curl -s "http://localhost:19999/api/v1/info"
```

### GET /api/v1/allmetrics
Export all metrics in various formats.

```bash
# Prometheus format
curl -s "http://localhost:19999/api/v1/allmetrics?format=prometheus"

# JSON format
curl -s "http://localhost:19999/api/v1/allmetrics?format=json"
```

### GET /api/v1/alarms
Get current alarm states.

```bash
curl -s "http://localhost:19999/api/v1/alarms"
```

## Common Charts

### System
- `system.cpu` - CPU usage by type
- `system.ram` - Memory usage
- `system.swap` - Swap usage
- `system.load` - Load averages (1, 5, 15 min)
- `system.io` - Disk I/O bytes
- `system.net` - Network bytes
- `system.processes` - Process states
- `system.entropy` - Available entropy
- `system.uptime` - System uptime

### Per-CPU
- `cpu.cpu0` through `cpu.cpuN` - Individual core usage

### Memory Details
- `mem.available` - Available memory
- `mem.committed` - Committed memory
- `mem.writeback` - Writeback activity
- `mem.kernel` - Kernel memory usage
- `mem.slab` - Slab allocator

### Disk
- `disk.sda` - Per-disk I/O (substitute actual device)
- `disk_space./` - Disk space for root
- `disk_ops.sda` - Disk operations
- `disk_await.sda` - Disk await time

### Network
- `net.eth0` - Per-interface traffic
- `net_packets.eth0` - Packet counts
- `net_errors.eth0` - Network errors

### Systemd Services
- `systemd_<service>.cpu` - Per-service CPU (user, system)
- `systemd_<service>.mem` - Per-service memory
- `systemd_<service>.io` - Per-service disk I/O
- `systemd_<service>.pids_current` - Per-service process count
- `systemd_<service>.pgfaults` - Per-service page faults

### Applications (apps plugin)
- `app.<group>_cpu_utilization` - CPU by application group
- `app.<group>_mem_usage` - Memory by application group
- `app.<group>_threads` - Thread count
- `app.<group>_processes` - Process count
- `app.<group>_fds_open` - Open file descriptors

## Time Formats

- Negative integers: seconds ago (`-3600` = 1 hour ago)
- Unix timestamp: absolute time (`1769174953`)
- Zero: now (`before=0`)

## Data Grouping

When requesting fewer `points` than available data:

| Group | Description |
|-------|-------------|
| `average` | Mean of values in period |
| `sum` | Sum of values |
| `min` | Minimum value |
| `max` | Maximum value |
| `median` | Median value |
| `stddev` | Standard deviation |

## Output Options

| Option | Effect |
|--------|--------|
| `objectrows` | Data as objects instead of arrays |
| `nonzero` | Only non-zero dimensions |
| `abs` | Absolute values |
| `null2zero` | Replace nulls with zeros |
| `seconds` | Timestamps as Unix seconds |
| `ms` | Timestamps as milliseconds |
| `flip` | Reverse time order |
