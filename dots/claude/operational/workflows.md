## Common Workflows

### Project Navigation

```bash
cd /realm/project/<name>    # Enter project
direnv allow                # Activate devshell (auto on cd)
```

### Workspace Inventory

For a fast read-only snapshot across many repos, use the shared scanner rather
than hand-rolling `find`/`git status` loops:

```bash
python3 /realm/project/sinnix/dots/_ai/tools/workspace_recon_scan.py --root /realm/project
python3 /realm/project/sinnix/dots/_ai/tools/workspace_recon_scan.py --root /realm/project --changed-only --with-size --json
```

### Heavy Agent Work

Recognized project dev environments install transparent wrappers for common
heavy commands. In Sinex and Polylogue devshells, ordinary commands such as
`xtask`, `cargo`, `pytest`, `uv`, `polylogue`, and `nix` are routed into the
Sinnix build/background slices automatically, so agents should run the normal
project command first.

Use an explicit scope only outside a recognized devshell or for one-off custom
commands that are expected to run for a long time or scan/write large stores:

```bash
sinnix-scope background -- <long-running scan/import/db command>
sinnix-scope build -- <project build/test command>
sinnix-scope nix-build -- nix build .#target
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
