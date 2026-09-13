# Declared activity

A thin local runtime for an activity declaration and its reconsideration boundary.
It does not infer behavior, score activities, demand productivity, or block applications.
Sinex remains the intended event/projection owner; this glue is replaceable.

## Desktop

**Super+F12** opens the centered **Now** workbench: latest chosen activity,
reconsideration boundary, and the next relevant actions. The high-contrast activity
card is not a claim about observed behavior. Choose next reveals the free-text form;
it accepts a duration (`30m`, `2h`), local clock (`00:00`), timezone-aware ISO time,
or a blank boundary for open-ended activity. Open-ended is the default.

Continue 15m/60m moves the boundary that far from **now**. Mark reviewed acknowledges
reconsideration but not activity completion. Return to chat opens the configured
continuation without acknowledgement. Pause/resume preserves the original boundary.
Timer-specific controls disappear when they do not apply. Successful changes close
the panel; failed commands retain the input and show an error.

**Super+Shift+F12**, or right-clicking the Now chip, opens **Catch a thought**.
Enter saves a literal fragment and closes; Shift+Enter adds a line; Escape keeps the
draft. Draft text is retained in the private activity directory across dismissal.
The field is focused when opened. Capturing never changes the activity, boundary,
acknowledgement, or notification budget.

`sinnix-activity note -- 'a fragment'` writes an `observation_captured` event into
the existing journal; `notes --limit 8 --json` reads recent fragments. Notes can be
captured before any activity is declared. Text is not automatically classified or
interpreted. Saved text, actor, recording time and declared activity context are
exportable through the same event interface.

The bar currently retains the separate operations/capabilities widgets. The design
calls for moving these to on-demand tools, but that presentation edit has not landed.

## Authority and persistence

`sinnix-activity` is the write interface. `activity.sqlite3` holds a singleton state,
append-only event history and notification receipts. `current.json` is a replaceable
read projection, refreshed by status, mutations and timer ticks. Source timestamps and
recording timestamps remain distinct. Actual behavior is not inferred from a declaration.

The state root is `SINNIX_ACTIVITY_STATE_DIR`, or `$XDG_STATE_HOME/sinnix/activity`
(default `~/.local/state/sinnix/activity`). The directory is 0700; files are 0600.
Sinnix's existing persistence of `.local/state/sinnix` covers this child.
Do not place real state, private continuation URLs or personal checkpoint contents in Git.

`import-checkpoint PATH` imports an explicit prior declaration into an empty store,
records path/hash provenance, and refuses to overwrite an existing allocation.
Repeating the identical import cannot rewind subsequent changes.
`export` emits JSONL events; `history --json` is a bounded recent view.
A corrupt or unsupported store fails visibly rather than silently becoming an empty day.

## Reconsideration delivery

`modules/services/activity.nix` uses the existing scheduled-job factory and runtime
surface registry. The user timer calls `tick --notify` every 30 seconds. Notification
attempts are limited to the due slot, +30 minutes, and +24 hours per checkpoint.
Missed slots coalesce: starting the machine after days does not produce three popups.
A failed submission consumes that slot and is recorded; the later slots are bounded
retry opportunities. Submission is not evidence of human notice. Check-in and pause
suppress delivery. A file lock serializes mutations with submission to avoid stale prompts.
Plain `tick` does not notify. No AI turn or continuously running custom daemon is needed.

For one-off bootstrap activation, install the Nix-generated command and user units;
do not maintain an independently handwritten timer. The workstation module owns the
same paths at the next regular system activation.

## Verification

`python3 -m unittest flake.tests.test_activity_runtime` exercises runtime and failure cases.
`LUAU_BIN=luau python3 -m unittest flake.tests.test_activity_desktop` executes synthetic
plugin callbacks and checks shell quoting, input dispatch and passive rendering.
`checks.<system>.activity-substrate` runs both plus Luau compilation. A real panel load
and notification submission are separate smoke tests; they are not implied by unit tests.
