#!/usr/bin/env python3
"""
Timewarrior Extension: Work-Life Balance Report
Shows time spent on work vs personal activities
"""

import sys
import json
from datetime import timedelta

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

    work_time = 0
    personal_time = 0
    other_time = 0

    for interval in intervals:
        tags = interval.get('tags', [])
        start = interval.get('start')
        end = interval.get('end')

        if not start or not end:
            continue

        # Calculate duration
        from datetime import datetime
        start_dt = datetime.fromisoformat(start.replace('Z', '+00:00'))
        end_dt = datetime.fromisoformat(end.replace('Z', '+00:00'))
        duration = (end_dt - start_dt).total_seconds()

        # Categorize
        if 'work' in tags or any(t in tags for t in ['coding', 'meetings', 'admin']):
            work_time += duration
        elif 'personal' in tags or any(t in tags for t in ['exercise', 'reading']):
            personal_time += duration
        else:
            other_time += duration

    total = work_time + personal_time + other_time

    print("\n" + "="*60)
    print("Work-Life Balance Report")
    print("="*60)

    if total > 0:
        print(f"\nWork:     {format_duration(work_time):>15} ({work_time/total*100:>5.1f}%)")
        print(f"Personal: {format_duration(personal_time):>15} ({personal_time/total*100:>5.1f}%)")
        print(f"Other:    {format_duration(other_time):>15} ({other_time/total*100:>5.1f}%)")
        print(f"\nTotal:    {format_duration(total):>15}")

        # Work-life balance score
        if work_time > 0:
            ratio = personal_time / work_time
            print(f"\nWork-Life Ratio: 1:{ratio:.2f}")

            if ratio < 0.3:
                print("⚠️  Warning: Low personal time. Consider better work-life balance.")
            elif ratio > 1.5:
                print("✓ Good work-life balance!")
    else:
        print("\nNo tracked time in the selected range.")

    print("="*60 + "\n")

if __name__ == '__main__':
    main()
