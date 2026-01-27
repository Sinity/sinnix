#!/usr/bin/env python3
"""Netdata metrics analyzer for system performance analysis.

Usage:
    python analyze.py summary              # Quick system overview
    python analyze.py diagnose             # Identify performance issues
    python analyze.py chart <name> [secs]  # Analyze specific chart
    python analyze.py export <name> [secs] # Export chart to CSV
    python analyze.py search <pattern>     # Find charts matching pattern
"""

import json
import subprocess
import sys
from urllib.request import urlopen
from urllib.parse import urlencode
from urllib.error import URLError

BASE_URL = "http://localhost:19999"

# Try to import rich for nice output, fall back to plain text
try:
    from rich.console import Console
    from rich.table import Table
    from rich.panel import Panel
    from rich import box
    console = Console()
    HAS_RICH = True
except ImportError:
    HAS_RICH = False
    console = None


def print_header(text: str):
    if HAS_RICH:
        console.print(Panel.fit(f"[bold]{text}[/bold]", style="cyan"))
    else:
        print(f"\n{'='*50}")
        print(f"  {text}")
        print(f"{'='*50}")


def print_warn(text: str):
    if HAS_RICH:
        console.print(f"[yellow]{text}[/yellow]")
    else:
        print(f"[WARN] {text}")


def print_error(text: str):
    if HAS_RICH:
        console.print(f"[red]{text}[/red]")
    else:
        print(f"[ERROR] {text}", file=sys.stderr)


def print_ok(text: str):
    if HAS_RICH:
        console.print(f"[green]{text}[/green]")
    else:
        print(f"[OK] {text}")


def print_bold(text: str):
    if HAS_RICH:
        console.print(f"[bold]{text}[/bold]")
    else:
        print(f"\n{text}")


def print_dim(text: str):
    if HAS_RICH:
        console.print(f"[dim]{text}[/dim]")
    else:
        print(f"  ({text})")


def fetch(endpoint: str, params: dict | None = None, silent: bool = False) -> dict | list | None:
    """Fetch from netdata API using urllib."""
    url = f"{BASE_URL}{endpoint}"
    if params:
        url += "?" + urlencode(params)
    try:
        with urlopen(url, timeout=10) as resp:
            return json.loads(resp.read().decode())
    except URLError as e:
        if not silent:
            print_error(f"API error: {e}")
        return None
    except json.JSONDecodeError as e:
        if not silent:
            print_error(f"JSON parse error: {e}")
        return None


def get_chart_data(chart: str, after: int = -300, points: int | None = None, silent: bool = False) -> dict | None:
    """Get data for a specific chart."""
    params = {"chart": chart, "after": after, "format": "json", "options": "objectrows"}
    if points:
        params["points"] = points
        params["group"] = "average"
    return fetch("/api/v1/data", params, silent=silent)


def get_charts() -> dict:
    """Get all available charts."""
    data = fetch("/api/v1/charts")
    return data.get("charts", {}) if data else {}


def find_service_charts(suffix: str) -> list[str]:
    """Find systemd service charts matching a suffix like 'cpu' or 'mem'."""
    charts = get_charts()
    # Match systemd_*.cpu, systemd_*.mem patterns (per-service metrics)
    matches = [cid for cid in charts.keys() if cid.startswith("systemd_") and cid.endswith(f".{suffix}")]
    return sorted(matches)


def summary():
    """Display system summary with key metrics."""
    print_header("System Metrics Summary")

    # CPU
    cpu = get_chart_data("system.cpu", after=-60, points=1)
    if cpu and cpu.get("data"):
        row = cpu["data"][0]
        total = sum(v for k, v in row.items() if k != "time" and isinstance(v, (int, float)))
        print_bold(f"CPU: {total:.1f}% total")
        breakdown = ", ".join(f"{k}={v:.1f}%" for k, v in row.items()
                             if k != "time" and isinstance(v, (int, float)) and v > 0.5)
        if breakdown:
            print(f"  {breakdown}")

    # Load
    load = get_chart_data("system.load", after=-60, points=1)
    if load and load.get("data"):
        row = load["data"][0]
        print_bold(f"Load: {row.get('load1', 0):.2f} / {row.get('load5', 0):.2f} / {row.get('load15', 0):.2f}")

    # Memory
    ram = get_chart_data("system.ram", after=-60, points=1)
    if ram and ram.get("data"):
        row = ram["data"][0]
        used = row.get("used", 0)
        cached = row.get("cached", 0) + row.get("buffers", 0)
        free = row.get("free", 0)
        total = used + cached + free
        print_bold(f"Memory: {used/1024:.1f}GB used, {cached/1024:.1f}GB cached, {free/1024:.1f}GB free (of {total/1024:.1f}GB)")

    # Disk I/O
    io = get_chart_data("system.io", after=-60, points=1)
    if io and io.get("data"):
        row = io["data"][0]
        read_kb = abs(row.get("in", 0))
        write_kb = abs(row.get("out", 0))
        print_bold(f"Disk I/O: read={read_kb:.0f} KB/s, write={write_kb:.0f} KB/s")

    # Network
    net = get_chart_data("system.net", after=-60, points=1)
    if net and net.get("data"):
        row = net["data"][0]
        recv = abs(row.get("received", 0)) / 1024
        sent = abs(row.get("sent", 0)) / 1024
        print_bold(f"Network: recv={recv:.1f} MB/s, sent={sent:.1f} MB/s")

    # Top systemd services by CPU
    services = find_service_charts("cpu")
    if services:
        print_bold("Top service CPU consumers:")
        usages = []
        for chart_id in services[:20]:  # Sample first 20
            data = get_chart_data(chart_id, after=-60, points=1, silent=True)
            if data and data.get("data"):
                row = data["data"][0]
                # Sum all dimensions
                total = sum(v for k, v in row.items() if k != "time" and isinstance(v, (int, float)))
                if total > 0.5:
                    name = chart_id.replace("systemd_", "").replace(".cpu", "")
                    usages.append((name, total))
        usages.sort(key=lambda x: x[1], reverse=True)
        for name, pct in usages[:5]:
            print(f"  {name}: {pct:.1f}%")


def diagnose():
    """Diagnose potential performance issues."""
    print_header("Performance Diagnosis")
    issues = []

    # Check CPU saturation
    cpu = get_chart_data("system.cpu", after=-300, points=60)
    if cpu and cpu.get("data"):
        totals = []
        for row in cpu["data"]:
            total = sum(v for k, v in row.items() if k != "time" and isinstance(v, (int, float)))
            totals.append(total)
        avg_cpu = sum(totals) / len(totals) if totals else 0
        max_cpu = max(totals) if totals else 0
        if avg_cpu > 80:
            issues.append(("HIGH CPU", f"Average {avg_cpu:.1f}% over last 5 min (peak {max_cpu:.1f}%)", "error"))
        elif max_cpu > 95:
            issues.append(("CPU SPIKES", f"Peak {max_cpu:.1f}% (avg {avg_cpu:.1f}%)", "warn"))

    # Check I/O wait
    if cpu and cpu.get("data"):
        iowaits = [row.get("iowait", 0) for row in cpu["data"]]
        avg_iowait = sum(iowaits) / len(iowaits) if iowaits else 0
        max_iowait = max(iowaits) if iowaits else 0
        if avg_iowait > 10:
            issues.append(("HIGH I/O WAIT", f"Average {avg_iowait:.1f}% - disk bottleneck likely", "error"))
        elif max_iowait > 20:
            issues.append(("I/O WAIT SPIKES", f"Peak {max_iowait:.1f}%", "warn"))

    # Check memory pressure
    ram = get_chart_data("system.ram", after=-300, points=60)
    if ram and ram.get("data"):
        for row in ram["data"]:
            used = row.get("used", 0)
            free = row.get("free", 0)
            total = used + free + row.get("cached", 0) + row.get("buffers", 0)
            if total > 0 and (used / total) > 0.9:
                issues.append(("MEMORY PRESSURE", ">90% memory used", "error"))
                break

    # Check swap usage (silent since swap may not exist on all systems)
    swap = get_chart_data("system.swap", after=-60, points=1, silent=True)
    if swap and swap.get("data"):
        row = swap["data"][0]
        used = row.get("used", 0)
        if used > 1024:  # >1GB swap
            issues.append(("SWAP IN USE", f"{used/1024:.1f}GB - memory pressure indicator", "warn"))

    # Check load average vs cores
    load = get_chart_data("system.load", after=-60, points=1)
    if load and load.get("data"):
        row = load["data"][0]
        load1 = row.get("load1", 0)
        # Assume 24 logical cores (from system context)
        if load1 > 24:
            issues.append(("OVERLOADED", f"Load {load1:.1f} exceeds core count (24)", "error"))
        elif load1 > 18:
            issues.append(("HIGH LOAD", f"Load {load1:.1f} approaching core count", "warn"))

    if issues:
        print_bold("Issues found:")
        for label, msg, level in issues:
            if level == "error":
                print_error(f"  {label}: {msg}")
            else:
                print_warn(f"  {label}: {msg}")
    else:
        print_ok("No significant issues detected")

    # Show top service resource consumers
    print_bold("Top service CPU consumers (last 5 min):")
    services = find_service_charts("cpu")
    usages = []
    for chart_id in services[:30]:
        data = get_chart_data(chart_id, after=-300, points=1, silent=True)
        if data and data.get("data"):
            row = data["data"][0]
            total = sum(v for k, v in row.items() if k != "time" and isinstance(v, (int, float)))
            if total > 0.1:
                name = chart_id.replace("systemd_", "").replace(".cpu", "")
                usages.append((name, total))
    usages.sort(key=lambda x: x[1], reverse=True)
    for name, pct in usages[:7]:
        print(f"  {name}: {pct:.1f}%")

    print_bold("Top service memory consumers:")
    services = find_service_charts("mem")
    usages = []
    for chart_id in services[:30]:
        data = get_chart_data(chart_id, after=-60, points=1, silent=True)
        if data and data.get("data"):
            row = data["data"][0]
            # mem charts often have 'ram' or similar dimensions
            total = sum(v for k, v in row.items() if k != "time" and isinstance(v, (int, float)))
            if total > 50:  # >50MB
                name = chart_id.replace("systemd_", "").replace(".mem", "")
                usages.append((name, total))
    usages.sort(key=lambda x: x[1], reverse=True)
    for name, mb in usages[:7]:
        print(f"  {name}: {mb:.0f} MB")


def chart_analysis(chart_name: str, seconds: int = 300):
    """Detailed analysis of a specific chart."""
    print_header(f"Chart: {chart_name}")

    data = get_chart_data(chart_name, after=-seconds)
    if not data or not data.get("data"):
        print_error(f"No data for chart '{chart_name}'")
        print("\nTry searching: python analyze.py search <pattern>")
        return

    rows = data["data"]
    labels = [k for k in rows[0].keys() if k != "time"]

    # Calculate statistics
    print_bold(f"Statistics (last {seconds}s):")
    print(f"  {'Dimension':<20} {'Min':>10} {'Max':>10} {'Avg':>10} {'Current':>10}")
    print(f"  {'-'*20} {'-'*10} {'-'*10} {'-'*10} {'-'*10}")

    for label in labels:
        values = [row.get(label, 0) for row in rows if isinstance(row.get(label), (int, float))]
        if values:
            print(f"  {label:<20} {min(values):>10.2f} {max(values):>10.2f} {sum(values)/len(values):>10.2f} {values[0]:>10.2f}")

    print_dim(f"Data points: {len(rows)}")


def export_csv(chart_name: str, seconds: int = 300):
    """Export chart data as CSV to stdout."""
    url = f"{BASE_URL}/api/v1/data?chart={chart_name}&after=-{seconds}&format=csv"
    try:
        with urlopen(url, timeout=30) as resp:
            print(resp.read().decode())
    except URLError as e:
        print_error(f"Export failed: {e}")
        sys.exit(1)


def search_charts(pattern: str):
    """Search for charts matching a pattern."""
    charts = get_charts()
    pattern_lower = pattern.lower()
    matches = [(cid, info) for cid, info in charts.items() if pattern_lower in cid.lower()]

    if not matches:
        print_warn(f"No charts matching '{pattern}'")
        return

    print_header(f"Charts matching '{pattern}'")
    print(f"  {'Chart ID':<40} {'Family':<15} {'Units':<15}")
    print(f"  {'-'*40} {'-'*15} {'-'*15}")

    for cid, info in sorted(matches)[:30]:
        print(f"  {cid:<40} {info.get('family', ''):<15} {info.get('units', ''):<15}")

    if len(matches) > 30:
        print_dim(f"...and {len(matches) - 30} more")


def main():
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)

    cmd = sys.argv[1].lower()

    if cmd == "summary":
        summary()
    elif cmd == "diagnose":
        diagnose()
    elif cmd == "chart":
        if len(sys.argv) < 3:
            print_error("Usage: analyze.py chart <chart-name> [seconds]")
            sys.exit(1)
        chart_name = sys.argv[2]
        seconds = int(sys.argv[3]) if len(sys.argv) > 3 else 300
        chart_analysis(chart_name, seconds)
    elif cmd == "export":
        if len(sys.argv) < 3:
            print_error("Usage: analyze.py export <chart-name> [seconds]")
            sys.exit(1)
        chart_name = sys.argv[2]
        seconds = int(sys.argv[3]) if len(sys.argv) > 3 else 300
        export_csv(chart_name, seconds)
    elif cmd == "search":
        if len(sys.argv) < 3:
            print_error("Usage: analyze.py search <pattern>")
            sys.exit(1)
        search_charts(sys.argv[2])
    else:
        print(__doc__)
        sys.exit(1)


if __name__ == "__main__":
    main()
