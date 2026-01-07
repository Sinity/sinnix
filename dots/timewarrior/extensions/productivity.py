#!/usr/bin/env python3
"""
Timewarrior Extension: Productivity Analysis
Analyzes productivity patterns by time of day and day of week
"""

import sys
import json
from collections import defaultdict
from datetime import datetime

def format_duration(seconds):
    """Format seconds as human-readable duration"""
    hours = int(seconds // 3600)
    minutes = int((seconds % 3600) // 60)
    return f"{hours}h {minutes}m"

def main():
    # Read input from timewarrior
    lines = sys.stdin.readlines()

    # Parse JSON data (timewarrior export returns array directly)
    intervals = json.loads(''.join(lines))

    by_hour = defaultdict(int)
    by_day = defaultdict(int)
    tag_stats = defaultdict(int)

    for interval in intervals:
        tags = interval.get('tags', [])
        start = interval.get('start')
        end = interval.get('end')

        if not start or not end:
            continue

        # Parse timestamps
        start_dt = datetime.fromisoformat(start.replace('Z', '+00:00'))
        end_dt = datetime.fromisoformat(end.replace('Z', '+00:00'))
        duration = (end_dt - start_dt).total_seconds()

        # Track by hour of day
        hour = start_dt.hour
        by_hour[hour] += duration

        # Track by day of week
        day = start_dt.strftime('%A')
        by_day[day] += duration

        # Track by tag
        for tag in tags:
            tag_stats[tag] += duration

    print("\n" + "="*60)
    print("Productivity Analysis")
    print("="*60)

    # Most productive hours
    print("\nMost Productive Hours:")
    sorted_hours = sorted(by_hour.items(), key=lambda x: x[1], reverse=True)[:5]
    for hour, duration in sorted_hours:
        print(f"  {hour:02d}:00 - {hour+1:02d}:00  {format_duration(duration):>15}")

    # Most productive days
    print("\nTime by Day of Week:")
    day_order = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday']
    for day in day_order:
        if day in by_day:
            print(f"  {day:10} {format_duration(by_day[day]):>15}")

    # Top tags
    print("\nTop Activities:")
    sorted_tags = sorted(tag_stats.items(), key=lambda x: x[1], reverse=True)[:10]
    for tag, duration in sorted_tags:
        print(f"  {tag:20} {format_duration(duration):>15}")

    print("="*60 + "\n")

if __name__ == '__main__':
    main()
