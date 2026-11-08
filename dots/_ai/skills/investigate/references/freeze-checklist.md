# Freeze checklist

The evidence directory must contain:

- manifest.json with UTC timestamp, repository root, branch, HEAD, and
  relative artifact paths.
- status.txt, reflog.txt, diff.patch, and cached.patch.
- conflicts/ copies of only the explicitly named files, with SHA-256 hashes
  in the manifest.

The freeze authorizes no repair. A separate operator decision must name the
exact file, ref, Beads record, service, or snapshot to mutate. Verify the
mutation against the frozen hash or state transition, then append the result
to the incident record.

## A frozen process (agent CLI or daemon)

Before killing it, record whether it spins or blocks and where:

- `ps -o pid,stat,etime,time,rss,nlwp,wchan:32 -p PID` and `/proc/PID/status`.
- Per-thread state and CPU ticks sampled twice a few seconds apart from
  `/proc/PID/task/*/stat`, with each thread's `wchan`: rising ticks mean
  spinning, a fixed `wchan` means blocked.
- `sudo cat /proc/PID/stack` (kernel stack) and
  `timeout 60 sudo gdb -p PID -batch -nx -ex 'set pagination off' -ex 'thread apply all bt 20'`.
- Open files (`ls -l /proc/PID/fd`) and sockets (`ss -xp`, `ss -tp`, filtered by `pid=PID`).
- The cgroup chain: memory/CPU limits on every ancestor slice, since a limit
  on a parent throttles the process while its own scope shows no events.
- Claude Code writes a per-launch debug log under `$CLAUDE_CODE_TMPDIR/claude-debug/`.
