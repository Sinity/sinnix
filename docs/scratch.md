# Managed scratch

Interactive sessions and the user manager use `/realm/tmp/work` as TMPDIR.
Declared AgentCTL operations with `scratch = "nvme"` create a private job
subdirectory and remove it on completion. Producers must honor inherited
TMPDIR and keep retained output outside it.

`sinnix-tmp-sweep` runs every 15 minutes. It recognizes Nix devshell scratch
and these invocation directories:

- `sinnix-chatgpt-native.<pid>.<random>`
- `sinnix-chatgpt-download.<pid>.<random>`
- `sinnix-router-poll.<pid>.<random>`

The PID is the allocating shell's BASHPID, captured before invoking mktemp.
These producers remove their directory on success, failure and catchable
HUP/INT/TERM. A crash can leave a directory behind. The sweeper considers it
only after 24 hours and only when that PID is absent from `/proc`. PID reuse
retains the directory. It rechecks the PID, directory identity and age before
removal. The existing Nix policy retains its holder checks and ten-minute
floor for `nix-develop-*`.

The privileged scan checks process cwd, root, executable, descriptors and
scratch environment variables, then drops to the selected owner for removal.
Incomplete process visibility refuses deletion. `--dry-run --owner USER`
reports eligible paths without removing them. Symlinks, foreign-owned trees,
`codex`, `claude-*` and names outside the recognized contracts are excluded.
Historical notes, logs, handoffs and other unqualified scratch names require
owner reconciliation; their age and prefix alone do not establish disposability.
