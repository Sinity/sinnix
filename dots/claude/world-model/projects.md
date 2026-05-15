## Project Constellation

### Core Infrastructure

| Project             | Path                             | Purpose                                                        |
| ------------------- | -------------------------------- | -------------------------------------------------------------- |
| **sinnix**          | `/realm/project/sinnix`          | NixOS system configuration (flake-parts, home-manager, agenix) |
| **sinex**           | `/realm/project/sinex`           | Event-driven data capture platform (Rust, NATS, PostgreSQL)    |
| **sinity-lynchpin** | `/realm/project/sinity-lynchpin` | Analysis coordination hub (Python, DuckDB, HPI-style modules)  |

### Capture & Integration Tools

| Project              | Path                              | Purpose                                                     |
| -------------------- | --------------------------------- | ----------------------------------------------------------- |
| **polylogue**        | `/realm/project/polylogue`        | AI chat export archiver (Claude, ChatGPT, Codex → Markdown) |
| **scribe-tap**       | `/realm/project/scribe-tap`       | Wayland keystroke mirror for Hyprland                       |
| **intercept-bounce** | `/realm/project/intercept-bounce` | Keyboard debouncing filter (Rust)                           |

### Knowledge & Analysis

| Project               | Path                               | Purpose                              |
| --------------------- | ---------------------------------- | ------------------------------------ |
| **knowledgebase**     | `/realm/data/knowledgebase`        | PKM vault (Obsidian-friendly MOCs)   |
| **knowledge-extract** | `/realm/project/knowledge-extract` | Adaptive knowledge assessment engine |
| **pwrank**            | `/realm/project/pwrank`            | Web-based ranking/preference tool    |

### Project Relationships

```
sinnix ──────► System packages, services, dotfiles
    │
    └──► Enables: sinex service stack, polylogued daemon, scribe-tap

sinex ◄────── Captures events from scribe-tap, polylogue
    │
    └──► Feeds: lynchpin via DuckDB/modules

lynchpin ◄─── Aggregates: ActivityWatch, Atuin, git, health, chats
    │
    └──► Produces: Calendar views, baselines, narratives
```

### Environment Variables (set by sinnix)

```
SINEX_ROOT=/realm/project/sinex
LYNCHPIN_REPO_ROOT=/realm/project/sinity-lynchpin
POLYLOGUE_ROOT=/realm/project/polylogue
KNOWLEDGEBASE_ROOT=/realm/data/knowledgebase
```

### Documentation Map

| Topic                 | Location                                                        |
| --------------------- | --------------------------------------------------------------- |
| Sinnix modules        | `/realm/project/sinnix/modules/`                                |
| Sinnix dotfiles       | `/realm/project/sinnix/dots/`                                   |
| Sinex architecture    | `/realm/project/sinex/AGENTS.md`                                |
| Lynchpin data sources | `/realm/project/sinity-lynchpin/docs/reference/data-sources.md` |
| Lynchpin roadmap      | `/realm/project/sinity-lynchpin/docs/plans/lynchpin-roadmap.md` |
| Realm topology        | `/realm/project/sinity-lynchpin/docs/reference/realm-map.md`    |
| Data inventory        | `/realm/data/INVENTORY.md`                                      |
