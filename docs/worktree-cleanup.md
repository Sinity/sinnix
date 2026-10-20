# Worktree cleanup

The daily `sinnix-worktree-reap` user service asks Worktrunk for worktrees integrated into each repository's default branch. Candidates must be at least one day old. Worktrunk recognizes merged, cherry-picked and squash-merged changes; an unmerged checkout stays registered.

Before each foreground removal, the command checks tracked, untracked and ignored files, refreshes integration, scans current process working directories, and rereads Git's worktree registration. Locked checkouts stay. Claude session locks are released only when the recorded PID is gone or its start time differs. An unreadable owner remains unknown and stops that repository's cleanup with a visible failure. Removal runs without force, process termination or project hooks.

Linux can hide a same-user process working directory even when its stat file is readable, for example for a non-dumpable user service manager. On a permission error, the command uses the host’s existing noninteractive sudo permission to read that one `/proc/<pid>/cwd` link. It adds no sudo policy. If that read also fails for a process that still exists, cleanup stops with a visible failure. Processes belonging to other users are outside this user service's observable session boundary. The scan checks working directories, not arbitrary open files or an application’s unsaved buffers. A process can still enter a checkout after the final probe; these checks do not reserve directories against arbitrary concurrent users.

Directories under `/realm/worktree` without `.git` are reported and retained with their permissions unchanged. Git's normal worktree removal deletes both the directory and its registration. A directory without `.git` therefore needs a separate ownership decision before deletion. Worktrunk owns its own removal trash and recovery semantics.

Failures are printed to the service journal and produce a nonzero exit status. Retained checkouts whose top-level directory is older than fourteen days are also reported for inspection; directory age alone does not establish inactivity or integration.

Run the isolated fixtures with `python3 scripts/tests/test_worktree_reap.py`, or use the `worktree-reap` flake check. The fixtures cover integration, retained files and locks, fresh process checks, unknown directories and visible command failure. They never invoke production cleanup.
