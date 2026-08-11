# Model Tiering and Launch Mechanics

Real campaigns mix Claude Code's own subagent dispatch (via `Agent`/`fork`)
with directly-launched non-Claude backends for cheap, high-volume narrow
passes. This reference covers picking the tier and the concrete mechanics
that worked. For the generic runtime-mode decision (local/background/cloud/
Kitty) and the shared launch helpers, defer to `agent-orchestration` — this
file only adds what audit campaigns specifically need on top.

## Picking a tier

| Region shape | Dispatch mechanism | Why |
|---|---|---|
| Dense/subtle logic, 3K-8K lines | Claude subagent, `subagent_type: review`, `model: opus` | Read-only adversarial reviewer type; needs the deepest judgment for cross-function invariant bugs. |
| Coverage-shaped, up to ~15K lines | Claude subagent, `subagent_type: review`, `model: sonnet` | Same tool, cheaper tier — the risk here is missed coverage, not missed subtlety. |
| Narrow 1-4 file narrate-through, 500-2500 lines | Direct fast/cheap external model (e.g. a Codex "spark"-tier model) via `codex exec` | An order of magnitude cheaper per-region; run dozens in parallel to cover ground a Claude-only campaign couldn't afford. Model dispatch doctrine (explicit model on every launch, no inherited defaults) applies here too even though these aren't Claude Code `Agent` calls — always name the model explicitly and confirm the launch receipt reports it. |

**Every fresh dispatch — Claude or otherwise — must name its model
explicitly.** `fork` is the only Claude-side exemption (inherits context+model
by design). This is enforced for `Agent` dispatches by a hard PreToolUse hook;
apply the same discipline by convention for external-backend launches, since
no hook covers those.

## Fast/cheap external model mechanics (Codex example)

These commands are Codex-specific but the pattern (scratch home directory to
strip unwanted global instructions, explicit sandbox mode, deterministic
last-message capture, bounded concurrency) generalizes to any CLI-driven
backend.

### Confirm the model slug is real before a batch

Don't trust a remembered or guessed model name — verify against the live
catalog first:

```bash
grep -o '"gpt-5[^"]*"' ~/.codex/models-v1.json | sort -u
```

A near-miss slug (e.g. guessing "code-spark" instead of the real
"codex-spark") fails or silently falls back; always confirm.

### Run without the global instructions file

If a campaign wants a narrow model reading only the target repo's own
project-level instructions (not the operator's global environment memory —
irrelevant context that just burns a small model's limited window), build a
scratch `CODEX_HOME` containing only what auth needs, with the global
instructions file omitted:

```bash
mkdir -p "$SCRATCH/codex-home-noagents"
cp ~/.codex/auth.json ~/.codex/config.toml ~/.codex/models-v1.json \
   "$SCRATCH/codex-home-noagents/"
# deliberately do NOT copy ~/.codex/AGENTS.md (or its symlink target)
```

Then pass `CODEX_HOME="$SCRATCH/codex-home-noagents"` as an env var on every
invocation. The repo's own project-level instructions file (if any) still
loads normally — this only strips the operator's cross-project global memory,
which is exactly the irrelevant-context weight you want off a tiny-context
model.

### The launch command shape

```bash
CODEX_HOME="$NOAGENTS_HOME" codex exec \
  -C <repo> \
  --model <slug> \
  -c 'model_reasoning_effort="high"' \
  -s read-only \
  --skip-git-repo-check \
  --output-last-message <out>.last.md \
  - < <prompt-file> \
  > <out>.log 2>&1
```

`-s read-only` is a real sandbox enforcement, not a prompt-level request —
use it for pure audit work so a model never needs to be trusted not to write.
`--output-last-message` gives a deterministic file to read for the final
report instead of tail-parsing a verbose log.

### Concurrency and batching

A shared per-user launcher wrapper script can race under high concurrency —
firing 6+ invocations at the exact same instant risked a `Text file busy`
error on the wrapper itself in practice. Batch concurrent launches (5 was a
safe number observed), and stagger the start of each launch within a batch
by 1-2 seconds rather than firing them all in the same instant. Retry any
individual launch that hits the race — it's a one-off infra collision, not a
systemic failure.

Do NOT add a hard `wait`-barrier between batches unless you actually need
one — a full wait-for-all-N-to-finish gate between every batch of 5
needlessly serializes the whole run to (batches × slowest-instance-time)
instead of (stagger-time + slowest-instance-time overall). The stagger alone
is enough to dodge the launcher race; barrier only if something downstream
genuinely needs the whole batch's results before the next batch can start
(rare for independent audit regions).

### The background-detach trap

Do not background a command by wrapping it in its own subshell —
`( some_command & )` — when you intend to `wait` for it later in the same
script. The subshell itself exits immediately after backgrounding its child,
which detaches that child from the parent shell's job table entirely; a
subsequent `wait` in the parent returns immediately having waited for
nothing, and the script proceeds believing all launches finished when they
may still be running. Background the command directly in the current shell
(`some_command &`, no wrapping subshell) so it stays in the job table `wait`
actually tracks.

## Verify before trusting a batch's output

A backgrounded batch that "completes" per its outer launcher script may still
have live grandchild processes still writing their output files — check that
output files have stopped growing (or that the actual process is gone from
`ps`) before treating a completion signal as "the reports are final," not
just "the launcher script returned."
