## Filesystem Structure

### /realm - The Data Kingdom

```
/realm/
├── project/           # All active project repositories
├── data/              # Canonical data lake (see below)
└── inbox/             # Staging area for retired/incoming data
```

User home is `/home/sinity`. It is intentionally not under `/realm`: the live
home directory is recreated on each boot and populated from `/persist` via the
impermanence module plus Home Manager activation. Persistent home state such as
SSH keys lives at `/persist/home/sinity/.ssh` and appears at runtime as
`/home/sinity/.ssh`.

### /realm/data - Data Lake Structure

```
/realm/data/
├── captures/          # Continuous local telemetry
│   ├── activitywatch/ # Window/AFK/browser tracking
│   ├── webhistory/    # Browser history exports
│   ├── asciinema/     # Terminal recordings
│   ├── keylog/        # Keystroke captures (scribe-tap)
│   ├── audio/         # Audio captures
│   ├── comms/         # Communication captures
│   ├── screenshot/    # Screenshots
│   ├── shell/         # Shell history (Atuin)
│   ├── syslog/        # System log exports
│   ├── machine/       # Canonical host machine telemetry
│   └── kitty-scrollback/ # Terminal scrollback
├── exports/           # GDPR/Takeout provider exports
│   ├── chatlog/       # AI chat archives (Claude, ChatGPT, Codex)
│   ├── health/        # Samsung Health, Sleep As Android
│   ├── google/        # Takeout archives
│   ├── reddit/        # Reddit GDPR export
│   ├── spotify/       # Streaming history
│   ├── raindrop/      # Raindrop bookmarks
│   ├── goodreads/     # Reading history
│   ├── wykop/         # Wykop export
│   ├── lastpass/      # Password manager export
│   └── comms/         # Messaging exports
└── libraries/         # Curated collections
    ├── finance/       # Ledger/accounting data
    ├── substack/      # Newsletter archives
    ├── doc/           # Document library
    └── model/         # Curated model data
```
