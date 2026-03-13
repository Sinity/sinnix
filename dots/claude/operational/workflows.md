## Common Workflows

### Project Navigation

```bash
cd /realm/project/<name>    # Enter project
direnv allow                # Activate devshell (auto on cd)
```

### Data Analysis (lynchpin)

```bash
cd /realm/project/sinity-lynchpin
just                        # List remaining heavyweight pipelines
just baseline               # Rebuild ActivityWatch/git/health rollups
python -m lynchpin.views.calendar_views build 2026-03-01 2026-03-07
```

### Context7

Use for unfamiliar APIs: `resolve-library-id` → `query-docs`. Cheap, prevents mistakes.
