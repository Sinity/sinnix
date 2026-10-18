# Declared activity

`sinnix-activity` records what you said you are doing and when you want to be
asked again (the check-in time). It does not infer behavior, score it, or block
applications.

## Desktop

**Super+F12** opens the **Now** panel: the current activity, its check-in
time, and actions. "Choose next" takes free text plus an optional duration
(`30m`, `2h`), a clock time (`00:00`), or an ISO time; leaving it blank means no
check-in. "Continue 15m/60m" moves the check-in time to that far from now.
"Mark reviewed" acknowledges a check-in without ending the activity. Pause and
resume keep the original check-in time.

**Super+Shift+F12**, or right-clicking the Now chip, opens **Catch a thought**:
Enter saves the text, Shift+Enter adds a line, Escape keeps the draft. A note
never changes the activity or its check-in. From a shell:
`sinnix-activity note -- 'text'` and `sinnix-activity notes --limit 8 --json`.

## State

State lives in `$XDG_STATE_HOME/sinnix/activity` (override with
`SINNIX_ACTIVITY_STATE_DIR`; directory 0700, files 0600, persisted with
`.local/state/sinnix`). `activity.sqlite3` holds the current state, the
append-only event history and notification records; `current.json` is a copy
of the declared state for the panel, rewritten only when that state changes;
time-derived fields such as the remaining time come from `status`. `export` prints all events as JSONL,
`history --json` the recent ones. `import-checkpoint PATH` seeds an empty
store and refuses to overwrite one. A corrupt store is reported as an error,
never treated as empty.

## Check-in notifications

`modules/services/activity.nix` runs `sinnix-activity tick --notify` every 30
seconds. Each check-in notifies at most three times: when due, 30 minutes
later, and 24 hours later. Missed times collapse into one, so booting after
days away does not produce a burst. Pausing or checking in stops them.

## Tests

`python3 -m unittest flake.tests.test_activity_runtime` and
`LUAU_BIN=luau python3 -m unittest flake.tests.test_activity_desktop`;
`checks.<system>.activity-substrate` runs both plus Luau compilation.
