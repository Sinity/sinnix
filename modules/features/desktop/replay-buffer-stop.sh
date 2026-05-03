#!/usr/bin/env bash
PIDFILE="/tmp/replay-buffer.pid"
if [[ -f "$PIDFILE" ]] && kill -0 "$(cat "$PIDFILE")" 2>/dev/null; then
  kill "$(cat "$PIDFILE")"
  rm -f "$PIDFILE"
  notify-send -t 2000 "Replay buffer stopped"
fi
