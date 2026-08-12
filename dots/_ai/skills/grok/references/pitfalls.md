# Pitfalls Log

Concrete failures hit running real audit campaigns, with the fix. Read this
before a first run — every one of these cost real time to diagnose once.

## Shell: backticks/complex quoting inside inline `--description`-style flags

A command-line tool argument built inline with backticks or nested quotes
(e.g. `--description "...uses \`some_command\`..."`) can trigger shell
command substitution instead of being passed literally, corrupting or
silently failing the whole command. Fix: never build multi-line or
code-quoting-heavy argument text inline. Write it to a file first via a
single-quoted heredoc delimiter (`cat > file.txt << 'EOF' ... EOF`— the
quotes around`EOF`prevent any interpolation), then pass`--flag "$(cat file.txt)"`. Command substitution results are not re-parsed
for further shell metacharacters, so this is safe even when the content
itself contains backticks, quotes, or `$`.

## Malformed heredoc leaving a shell-command tail in the payload

An improperly terminated heredoc (delimiter typo, mismatched indentation)
lets the _next_ shell command's own tail text leak literally into whatever
argument was mid-construction, and error-recovery code paths can silently
substitute a placeholder ("see description above") instead of failing loudly.
Always verify a just-created record's actual stored content (re-fetch it)
after any multi-part construction, especially the first time you use a new
heredoc pattern in a session — don't assume the write succeeded as intended.

## Concurrent CLI launches racing a shared wrapper script

Firing many concurrent invocations of a tool that goes through a shared,
possibly self-updating launcher wrapper can produce a `Text file busy` (or
equivalent) error on the wrapper file itself under high simultaneous
concurrency — a real infra race, not a fault in the tool or the task. Fix:
cap concurrent launches to a modest batch size (5 was safe in practice),
stagger individual launches within a batch by a second or two rather than
firing them in the same instant, and simply retry any individual launch that
hits the race afterward.

## The background-detach subshell mistake

`( some_command & )` — wrapping a backgrounded command in its own subshell —
detaches it from the parent shell's job table the instant the subshell exits
(which happens almost immediately, since there's nothing else in it). A
subsequent `wait` in the parent script returns having waited for nothing; the
script proceeds believing everything finished while the actual work may
still be running in the background, unmonitored. Symptom: a "launched N
things, waited, all done" log message followed minutes later by output files
that are still visibly growing. Fix: background the command directly
(`some_command &`) with no wrapping subshell.

## Overly conservative batch-then-barrier serialization

Related to the above but distinct: even with correct backgrounding, adding a
full `wait`-for-the-whole-batch barrier between every batch when only a
launch-time stagger was actually needed serializes total wall-clock to
(number of batches × slowest single instance) instead of (stagger time +
slowest single instance overall) — a 5-10x unnecessary slowdown on a large
batch. Only barrier between stages when something downstream genuinely
depends on the whole prior batch's results.

## Agent turn-budget exhaustion with zero final report

A deep investigation-shaped subagent can burn its entire turn budget on real,
non-repetitive investigation and simply run out of room before ever
synthesizing a findings report — producing either a single throwaway
fragment or literally no final text. Fix that reliably worked: resume the
_same_ agent (not a fresh dispatch with the same prompt) with a blunt
instruction to stop investigating and write up now, based on whatever it's
already found. Resuming preserves all the accumulated investigation context
a fresh dispatch would discard. Don't diagnose this as "the turn cap is too
low" and just raise the numeric ceiling — that doesn't teach an agent to
reserve room for writeup, it just moves the same wall further out. The fix
that actually addresses the failure mode is a standing instruction: "the
turn cap is a last-resort backstop, not a budget to conserve against — the
one non-negotiable rule is never end the run in pure silence." A report
covering partial ground with the gaps stated is a fully legitimate outcome;
total loss of the accumulated work is not.

## Forks cannot nest; deep hierarchical decomposition isn't free

If your runtime's context-sharing "fork" primitive exists, it typically
cannot spawn further forks of itself — only fresh, non-context-sharing
dispatches can be nested, which forfeits the cheap-context-sharing property
that makes forking attractive in the first place, and combinatorial fanout
(N children × M grandchildren × ...) grows expensive fast with no
central-dedup mechanism at each level. In practice, one well-grounded flat
partition (measure real sizes, define regions, dispatch once) with a single
coordinator doing central cross-referencing outperforms recursive
self-organizing decomposition for most codebase sizes — the actual
bottleneck tends to be the coordinator's own throughput processing results,
not dispatch depth. Reach for one extra level selectively (a single region's
own agent spawning 2-3 focused sub-investigations if it hits something
unusually large/tangled) rather than planning a fixed multi-level recursive
strategy up front.

## Reimport/tracker-sync hazards during a campaign

If the audit's own tracker state lives in a version-controlled file that
gets reimported/resynced on certain operations (a checkout, a worktree
touch, even a read-only query in some trackers), a stale worktree or
checkout can silently overwrite concurrent coordinator writes. Keep
worker/delegate dispatches read-only with respect to the tracker where
possible; have the coordinator own all tracker mutations and re-verify state
after any operation known to trigger a resync, rather than trusting a
single write to have stuck.
