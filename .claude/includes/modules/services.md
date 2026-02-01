## Services (Daemons)

Long-running systemd services in `modules/services/`:

| Service | Purpose | Has UI? |
|---------|---------|---------|
| sinex.nix | Data capture platform (Rust/NATS/PostgreSQL) | No (background) |
| netdata.nix | System monitoring metrics collection | Yes (web UI) |
| terminal-capture.nix | Shell session recording (transparent capture) | No (background) |
| transmission.nix | BitTorrent daemon | Yes (web UI) |

**Rule**: Primary purpose is **daemon**, UI is secondary/optional. Compare with `features/desktop/activitywatch.nix` where user wants **tracking**, daemon is implementation detail.
