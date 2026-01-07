#!/usr/bin/env python3
"""
Taskwarrior Hook: Review tracking
Updates the 'reviewed' UDA when a task is modified
"""

import sys
import json
from datetime import datetime

def main():
    original = sys.stdin.readline()
    modified = sys.stdin.readline()

    original_task = json.loads(original)
    modified_task = json.loads(modified)

    # Update reviewed date when task is examined/modified
    # (excluding automated modifications)
    if modified_task.get('status') == 'pending':
        modified_task['reviewed'] = datetime.utcnow().strftime('%Y%m%dT%H%M%SZ')

    print(json.dumps(modified_task))
    sys.exit(0)

if __name__ == '__main__':
    main()
