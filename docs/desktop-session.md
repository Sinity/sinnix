# Desktop session restore

Run `sinnix reboot` from the logged-in desktop to save its current state and
reboot. If the snapshot service fails, the command exits before requesting
the reboot. A plain `systemctl reboot` uses the last successful snapshot.
The graphical session starts the snapshot timer, which runs once a minute.
Logging out stops the timer and the service.

The user manager runs `sinnix-desktop-restore.service` after Noctalia starts.
It can launch windows while the compositor is locked. It uses the newest
snapshot from the preceding boot recorded in the system journal. Restore
attempts run once per boot. A fresh boot with no matching snapshot records
that fact and starts no applications.

- Kitty reopens its OS windows, tabs, pane titles and saved directories.
  Hyprland puts the windows on their saved numbered workspaces when the
  process ID and window title identify the workspace. Each OS window is
  launched separately so its workspace can be assigned before it opens.
  Windows with ambiguous placement open on the default workspace and the
  receipt records the ambiguity. The compositor chooses the tile geometry.
- The captured shell resumes a foreground Claude Code or Codex conversation
  with `claude --resume <id>` or `codex resume <id>`. Restore uses the live
  Claude registry or the Codex process's open rollout file to identify a
  conversation. A shell opens when the original process had no identifiable
  conversation. A missing working directory falls back to the home directory.
- If Chrome was running, Sinnix launches `sinnix-chrome`. Chrome opens its
  previous tabs through its own session restore setting.
- The notification and receipt list interrupted AgentCTL jobs by job ID
  and numeric task ID. AgentCTL retries the same task only when its saved
  running attempt was killed, its launch and descriptor allow reboot retry,
  and the retained input is usable. Queued tasks stay with pueue. See
  [AgentCTL reboot recovery](agentctl.md#reboot-recovery).

The three latest snapshots and `restore.json` live under
`${XDG_STATE_HOME:-$HOME/.local/state}/sinnix/session/`. Files are private
because they contain terminal titles, paths, and conversation IDs. The
receipt records launch requests and job retries. Use the programs' own
clients to see what opened. The user journal records the restore service
result.

The restored conversations wait for input. In-flight agent turns, shell
state, scrollback, running commands, SSH sessions, unsaved editor buffers,
in-page browser state, and cached key unlocks end with the old processes.
Temporary files in `/tmp` disappear and boot sets agent scratch directories
aside. Kitty windows managed by the WeeChat scratchpad start through their
own service.
