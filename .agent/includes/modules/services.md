## Services (Daemons)

Long-running systemd services in `modules/services/`:

| Service               | Purpose                                        | Has UI?         |
| --------------------- | ---------------------------------------------- | --------------- |
| agent-gateway.nix     | Trusted local MCP gateway for coding agents    | No (MCP/HTTP)   |
| below.nix             | Facebook's cgroup resource monitoring          | Yes (TUI)       |
| lynchpin.nix          | Data analysis hub (Python/DuckDB)              | No (background) |
| machine-telemetry.nix | Canonical host telemetry for Lynchpin analysis | No (background) |
| oracle.nix            | Daily reverse-prompting digest (timer+oneshot) | No (background) |
| polylogue.nix         | AI chat archive ingestion (via HM module)      | No (background) |
| sinex.nix             | Data capture platform (Rust/NATS/PostgreSQL)   | No (background) |
| terminal-capture.nix  | Shell session recording (transparent capture)  | No (background) |
| transmission.nix      | BitTorrent daemon                              | Yes (web UI)    |

**Rule**: Primary purpose is **daemon**, UI is secondary/optional. Compare with `features/desktop/activitywatch.nix` where user wants **tracking**, daemon is implementation detail.
