#!/bin/sh
# Runs on sinnix-gw via `ssh sinnix-gw sh -s -- <period> [<period> ...]`.
# Only invoked when the routine poll (remote-poll.sh) surfaces a nlbwmon
# period this lane hasn't captured yet -- first-run backfill of all closed
# months, then at most once a month thereafter, since closed months are
# immutable.
set -e
for p in "$@"; do
  echo "===NLBW_PERIOD:$p==="
  nlbw -c csv -t "$p" 2>/dev/null || true
done
