# Sinity Environment Memory

> **This file is your persistent environment memory.** It contains compressed understanding of the entire development ecosystem, NixOS configuration, and project constellation. You start every session "pre-grokked".

---

## Behavioral Rules

**§1 Echo scope**: On multi-step/ambiguous requests:
```
ECHO(Understanding: X targeting Y, excluding Z)
```

**§2 Stay in scope**: Don't expand without asking:
```
ECHO(Should I also include X?)
```

**§3 Confirm destructive**: Before destructive operations:
```
ECHO(Confirming: about to delete X. Proceed?)
```

**§4 Batch edits**: Foresee all changes, apply together. No fix-one-error-at-a-time.

**§5 Brevity first**: Skip summaries when clear. `ECHO(Done.)` suffices.

**§6 Right tools**: Glob not bash+find. Parallel reads. Context7 before guessing APIs.

**§7 Error recovery**: Assess full scope → batch related fixes → verify. Order: blockers → types → warnings.

**§8 Frustration signals**: On "YAGNI", curt responses, "come on" — stop elaborating, simplify, act.

**§9 Git**: Report steps with ECHO, atomic commits, no push unless asked:
```
ECHO([git:stage/commit] 2 files, "fix: validation bypass")
```

**§10 Completion discipline**: Don't stop until goal achieved or explicitly blocked. If agents fail, diagnose and retry or escalate.

**§11 History awareness**: When context seems missing or user references past work, proactively search session history.

**§12 Cross-reference verification**: When analyzing code, check related functions use consistent patterns. Don't assume consistency.

---

## Notation Conventions

Commands and prompts use lightweight structural notation. Not parsed as code—just aids clarity.

```
STRUCTURAL:
  PARALLEL:     execute concurrently
  SEQUENTIAL:   execute in order
  FOR EACH x:   iterate
  IF/THEN/ELSE: conditional

FLOW:
  →             leads to, produces, then
  |             alternatives (x | y | z)

EMPHASIS:
  !!!           critical constraint, must not violate

OUTPUT:
  ECHO(text)    output this text literally, including ECHO() wrapper
                used for: confirmations, status, standardized formats
  ECHO(>>> ...) output AND pause for user input before continuing
                the >>> prefix signals "wait for response"

MATCHING:
  MATCH x:
    | pattern → action
    | _       → default
```

### ECHO() Examples

```
ECHO(Understanding: refactor auth module, excluding tests)
ECHO([git:stage/commit] 2 files, "fix: validation bypass")
ECHO(>>> Which files to analyze? "all" | specific selection)
```

The agent outputs text inside ECHO() verbatim. When >>> appears, wait for user response before continuing.

---

## Hard Blocks (PreToolUse hooks enforce these)

The following are blocked at runtime via hooks. Don't attempt:
- `rm -rf` or similar destructive recursive deletes → use `trash` or backup first
- Imperative package installs: `nix profile install`, `cargo install`, `pip install`, `npm install -g` → use declarative config
- `git push --force` to main/master → never

---

## System Context

### Hardware
- **Host**: `sinnix-prime` (desktop workstation)
- **CPU**: Intel i7-13700K (16 cores, 24 threads)
- **OS**: NixOS 26.05 (Yarara) - unstable channel

### NixOS Environment
```
# NEVER use nix profile commands - all packages via modules
# Use nix shell/nix develop for temporary tools

direnv allow           # Activate project devshell
nix develop            # Enter flake devshell manually
nix build .#<output>   # Build specific flake output
```

---

## Filesystem Structure

### /realm - The Data Kingdom
```
/realm/
├── project/           # All active project repositories
├── data/              # Canonical data lake (see below)
├── home/              # User home directory (symlinked from ~)
├── inbox/             # Staging area for retired/incoming data
└── knowledgebase/     # PKM vault (Obsidian/Dendron)
```

### /realm/data - Data Lake Structure
```
/realm/data/
├── captures/          # Continuous local telemetry
│   ├── activitywatch/ # Window/AFK/browser tracking
│   ├── webhistory/    # Browser history exports
│   ├── asciinema/     # Terminal recordings
│   └── keylog/        # Keystroke captures (scribe-tap)
├── exports/           # GDPR/Takeout provider exports
│   ├── chatlog/       # AI chat archives (Claude, ChatGPT, Codex)
│   ├── reddit/        # Reddit GDPR export
│   ├── spotify/       # Streaming history
│   ├── google/        # Takeout archives
│   ├── health/        # Samsung Health, Sleep As Android
│   └── ...            # Other service exports
├── libraries/         # Curated collections
│   ├── finance/       # Ledger/accounting data
│   └── substack/      # Newsletter archives
└── indices/           # Derived stores (qdrant, sinevec)
```

---

## Project Constellation

### Core Infrastructure

| Project | Path | Purpose |
|---------|------|---------|
| **sinnix** | `/realm/project/sinnix` | NixOS system configuration (flake-parts, home-manager, agenix) |
| **sinex** | `/realm/project/sinex` | Event-driven data capture platform (Rust, NATS, PostgreSQL) |
| **sinity-lynchpin** | `/realm/project/sinity-lynchpin` | Analysis coordination hub (Python, DuckDB, HPI-style modules) |

### Capture & Integration Tools

| Project | Path | Purpose |
|---------|------|---------|
| **polylogue** | `/realm/project/polylogue` | AI chat export archiver (Claude, ChatGPT, Codex → Markdown) |
| **scribe-tap** | `/realm/project/scribe-tap` | Wayland keystroke mirror for Hyprland |
| **intercept-bounce** | `/realm/project/intercept-bounce` | Keyboard debouncing filter (Rust) |

### Knowledge & Analysis

| Project | Path | Purpose |
|---------|------|---------|
| **knowledgebase** | `/realm/project/knowledgebase` | PKM vault (Obsidian-friendly MOCs) |
| **knowledge-extract** | `/realm/project/knowledge-extract` | Adaptive knowledge assessment engine |
| **pwrank** | `/realm/project/pwrank` | Web-based ranking/preference tool |

### Project Relationships
```
sinnix ──────► System packages, services, dotfiles
    │
    └──► Enables: sinex-ingestd, polylogue-daemon, scribe-tap

sinex ◄────── Captures events from scribe-tap, polylogue
    │
    └──► Feeds: lynchpin via DuckDB/modules

lynchpin ◄─── Aggregates: ActivityWatch, Atuin, git, health, chats
    │
    └──► Produces: Calendar views, baselines, narratives
```

---

## Sinnix Configuration (NixOS)

### Structure
```
sinnix/
├── flake.nix              # Inputs + outputs
├── hosts/
│   ├── sinnix-prime/      # Desktop workstation
│   └── sinnix-ethereal/   # Secondary machine
├── modules/
│   ├── bundles/           # desktop.nix, dev.nix
│   ├── features/          # cli/, desktop/, dev/
│   ├── services/          # sinex.nix, polylogue.nix
│   └── projects.nix       # Defines /realm/project/* paths
└── dots/                  # Dotfile configurations
    ├── qutebrowser/
    ├── hyprland/
    ├── claude/, codex/    # AI tool configs
    └── ...
```

### Key Module Patterns
```nix
# Enable features
sinnix.bundles.desktop.enable = true;
sinnix.features.dev.editors.vscode.enable = true;
sinnix.services.sinex.enable = true;

# Project paths available as:
config.sinnix.projects.sinex      # /realm/project/sinex
config.sinnix.projects.lynchpin   # /realm/project/sinity-lynchpin
```

### Environment Variables (set by sinnix)
```
SINEX_ROOT=/realm/project/sinex
LYNCHPIN_REPO_ROOT=/realm/project/sinity-lynchpin
POLYLOGUE_ROOT=/realm/project/polylogue
KNOWLEDGEBASE_ROOT=/realm/project/knowledgebase
```

---

## Common Workflows

### Project Navigation
```bash
cd /realm/project/<name>    # Enter project
direnv allow                # Activate devshell (auto on cd)
```

### Desktop Environment
- **WM**: Hyprland (Wayland compositor)
- **Browser**: qutebrowser (keyboard-driven)
- **Terminal**: foot/kitty
- **Launcher**: tofi

### Data Analysis (lynchpin)
```bash
cd /realm/project/sinity-lynchpin
just                        # List available pipelines
just baseline               # Rebuild ActivityWatch/git/health rollups
just calendar-refresh ...   # Generate daily views
```

---

## Documentation Map

| Topic | Location |
|-------|----------|
| Sinnix modules | `/realm/project/sinnix/modules/` |
| Sinnix dotfiles | `/realm/project/sinnix/dots/` |
| Sinex architecture | `/realm/project/sinex/AGENTS.md` |
| Lynchpin data sources | `/realm/project/sinity-lynchpin/docs/reference/data-sources.md` |
| Lynchpin roadmap | `/realm/project/sinity-lynchpin/docs/plans/lynchpin-roadmap.md` |
| Realm topology | `/realm/project/sinity-lynchpin/docs/reference/realm-map.md` |
| Data inventory | `/realm/data/INVENTORY.md` |

---

## Context7

Use for unfamiliar APIs: `resolve-library-id` → `query-docs`. Cheap, prevents mistakes.

---

## Session History & Continuity

### When to Look Up History

**Proactive triggers** (do without being asked):
- User references past work: "remember when...", "like before", "that thing we did"
- After context compaction loses relevant earlier work
- Task feels familiar but details are missing
- Error patterns that might have been solved before

**How to access**:
```bash
# Current project sessions
ls -lt ~/.claude/projects/<project>/*.jsonl | head -10

# Search across sessions
grep -r "pattern" ~/.claude/projects/*/

# Read specific session
cat ~/.claude/projects/<project>/<session-id>.jsonl | jq -r 'select(.type=="user") | .content' | head -100
```

**Use `/history` command** for guided access.

### Persistent Learning

When accessing history, write down learnings to prevent re-discovery:

1. **Session summaries**: `.claude/history-summaries/<id>.md`
2. **Cross-session patterns**: `.claude/learnings.local.md`
3. **Recurring solutions**: Add to relevant CLAUDE.md

---

## Codebase Analysis Workflow

### Survey → Narrate → Synthesize

For thorough code review or bug hunting, use `/swarm` with preset `analyze`:

1. **Survey** (BFS): List all items at current level (crates/modules/files), note concerns without deep-diving
2. **Narrate** (DFS): For highest-concern item, verbalize line-by-line what each piece does
3. **Synthesize**: Return to broad view, cross-reference findings across related code

This is operationalized via `/swarm analyze <target>`.

### Concrete Bug-Finding Techniques

These actually work (empirically validated on sinex codebase):
- **Line-by-line narration**: Verbalizing forces attention, surfaced 16 bugs in one session
- **Cross-reference related functions**: Comparing `register()` vs `list()` found key format mismatch
- **Check get→modify→put patterns** for race conditions in distributed code

### Analysis Commands

- `/analyze <target>` - Interactive analysis with user steering (survey → narrate → synthesize)
- `/swarm analyze <target>` - Autonomous parallel analysis

### Session Commands

- `/meta` - Review session friction/successes, propose config improvements
- `/recap` - Generate handoff summary
- `/checkpoint` - Save/restore cognitive state
- `/history` - Search past sessions

---

## Thinking in Markdown

Externalize reasoning to scratch files. Write liberally - context is expensive, files are cheap.

### When to Create Scratch Files

- **Always**: Non-trivial analysis, multi-step debugging, architectural decisions
- **Proactively**: Anything you figure out that took >1 tool call to discover
- **Especially**: Cross-session work, context-compaction-spanning tasks

### File Locations

| Scope | Location | Use |
|-------|----------|-----|
| Global/cross-project | `~/.claude/scratch/NNN-<topic>.md` | System-wide learnings, config work |
| Project-specific | `.claude/scratch/NNN-<topic>.md` | Project analysis, debugging notes |

### File Structure

```yaml
---
created: "ISO timestamp"
purpose: "brief description"
status: "active | complete | abandoned"
project: "sinex | polylogue | etc"  # if project-specific
---

# Topic

## Context
[what prompted this]

## Findings
[discoveries, analysis]

## Outcome
[results, decisions made]
```

### Proactive Usage

```
MATCH situation:
  | debugging session found root cause  → write scratch note
  | explored unfamiliar code area       → document what you learned
  | made non-obvious decision           → capture rationale
  | user asked "how does X work"        → write explanation, then summarize to user
```

When referring user to a scratch file, **always summarize the key points** in your response - don't just point at the file.

### Lifecycle

1. **Create liberally** - low cost, high value for future sessions
2. **Update as you go** - append findings during work
3. **Archive when complete**: `mv NNN-*.md archive/`
4. **Pin in CLAUDE.md** if ongoing relevance (see below)

### Pinning in Project CLAUDE.md

Projects can maintain a "Pinned Notes" section that **transcludes** scratch files using `@path` syntax:

```markdown
## Pinned Notes

@.claude/scratch/003-replay-bug-hunt.md
@.claude/scratch/007-schema-v5-migration.md
```

**Key behaviors:**
- `@` transcludes file content into CLAUDE.md at session startup
- Works with project-relative (`.claude/scratch/...`) and absolute (`@~/.claude/scratch/...`) paths
- Max 5 hops of recursive imports
- NOT evaluated inside code blocks - must be bare `@path` on its own line
- Run `/memory` to see what files are loaded

This automatically includes scratch file content without bloating CLAUDE.md itself.

### vs /checkpoint

- `/checkpoint` → full cognitive state for session handoff
- Scratch files → specific topic working documents

---

## Project CLAUDE.md Philosophy

Project-level CLAUDE.md files prevent repeated exploration.

### Core Purpose

**Exploration cost per subsystem**: ~15-30K tokens
**CLAUDE.md loading cost**: ~5-10K tokens once
**ROI**: After 2-3 sessions, pays for itself

### Standard Structure

```
# Project Name

> Meta blurb: update triggers, philosophy ref

## Quick Reference / Core Architecture
[Most-used commands, key architecture table]

## Critical Files / Crate Reference
[Organized by layer/purpose, with behaviors]

## Patterns (DO/DON'T)
[Correct usage with code examples]

## Configuration / Environment
[Inline values, not references]

## Pinned Notes                          ← NEW
[Links to .claude/scratch/*.md]

## Troubleshooting / Common Debugging
[Error → diagnostic checklist format]

## Maintenance Protocol
[Update triggers, verification steps]
```

### Knowledge Tiers

| Tier | Type | Document? |
|------|------|-----------|
| 1-2 | Navigation, Patterns | YES - stable, high leverage |
| 3-4 | Behavior, Operations | YES - volatile but valuable |
| 5 | Implementation details | NO - changes constantly |

### Format Principles

```
MATCH content_type:
  | multi-dimensional data → tables
  | patterns               → DO/DON'T with code
  | troubleshooting        → diagnostic checklists
  | values                 → inline, not references
  | examples               → one good, not three mediocre
```

**Bad**: "The system has checkpointing."
**Good**: "Checkpoints: NATS KV primary, file backup, saves every 1000 events OR 10s"

### Self-Maintenance

Update CLAUDE.md in **same commit** as behavioral changes. Exploration → discovery → document immediately (same session).

---

## Project-Specific Context

Each project has its own `AGENTS.md` or `CLAUDE.md` with deeper context:
- **sinex**: Comprehensive crate map, patterns, test utilities
- **sinnix**: Module organization, feature toggles
- **lynchpin**: Data landscape, pipeline specs, Lynchpin API

When working in a project directory, that project's instructions take precedence.

---

## Technical Reference

### System Architecture
- **NixOS Configuration**: Uses `modules/default.nix` as entrypoint.
- **Core Stack**: `modules/core.nix`, `networking.nix`, `storage.nix`, etc.
- **Services**: Grouped in `modules/services/`. `sinex.nix` is the unified data platform.
- **Features**: Grouped in `modules/features/` (`cli`, `desktop`, `dev`).
- **Hosts**: Defined in `hosts/`, layered on top of shared modules.
- **Secrets**: Managed via `modules/secrets.nix` using agenix.

### Dotfile Management
- **Location**: `dots/` directory.
- **Mechanism**: Home Manager out-of-store symlinks (`mkOutOfStoreSymlink`). Edits propagate instantly without rebuild.
- **Key Managed Paths**:
  - `dots/claude/` -> `~/.config/claude`
  - `dots/nvim/` -> `~/.config/nvim`
  - `dots/vscode/` -> VS Code profile
  - `dots/hyprland/` (Some parts declarative in Nix)

### Tooling: Codex CLI
- **Config**: `dots/codex/config.toml`, skills in `dots/codex/skills`.
- **MCP Servers**: GitHub, PostgreSQL (local), Qdrant, Context7, Firecrawl, `cclsp` bridge.
- **Context7**: Documentation discovery via `resolve-library-id` and `get-library-docs`.
- **LSP Bridge**: `cclsp` shares manifests between Claude, Codex, and OpenCode. uses `lsp-root` for project detection.

