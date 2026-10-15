#!/bin/sh
# Runs on sinnix-gw via `ssh sinnix-gw sh -s -- <period> [<period> ...]`.
# Only invoked when the routine poll (remote-poll.sh) surfaces a nlbwmon
# period this lane hasn't captured yet -- first-run backfill of all closed
# months, then at most once a month thereafter, since closed months are
# immutable.
set -e
for p in "$@"; do
  # A failed or absent export is unavailable, not a measured empty month.
  # Emit its delimiter only after the complete command succeeds; the caller
  # must not mark this immutable period captured before it can be retried.
  csv="$(nlbw -c csv -t "$p")"
  if [ -z "$csv" ]; then
    echo "capture-router: empty nlbw export for period $p" >&2
    exit 1
  fi
  echo "===NLBW_PERIOD:$p==="
  printf '%s\n' "$csv"
done
