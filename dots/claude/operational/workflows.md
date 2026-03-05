## Common Workflows

### Project Navigation

```bash
cd /realm/project/<name>    # Enter project
direnv allow                # Activate devshell (auto on cd)
```

### Data Analysis (lynchpin)

```bash
cd /realm/project/sinity-lynchpin
just                        # List available pipelines
just baseline               # Rebuild ActivityWatch/git/health rollups
just calendar-refresh ...   # Generate daily views
```

### Context7

Use for unfamiliar APIs: `resolve-library-id` → `query-docs`. Cheap, prevents mistakes.
