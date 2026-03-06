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
└── runtime/           # Mutable service state (e.g. sinex spool/blob repo)
```
