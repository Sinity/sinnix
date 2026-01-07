#!/usr/bin/env python3
"""
Taskwarrior Hook: Auto-tag inbox
Automatically adds +inbox tag to new tasks that don't have a project
"""

import sys
import json

def main():
    original = sys.stdin.readline()
    modified = json.loads(original)

    # If task has no project and no inbox tag, add inbox tag
    if 'project' not in modified or not modified['project']:
        tags = modified.get('tags', [])
        if 'inbox' not in tags:
            tags.append('inbox')
            modified['tags'] = tags

    print(json.dumps(modified))
    sys.exit(0)

if __name__ == '__main__':
    main()
