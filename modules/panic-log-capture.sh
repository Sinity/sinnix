#!/usr/bin/env bash
panic_dir="/realm/data/captures/syslog/panic"
if [ -d /sys/fs/pstore ] && [ "$(ls -A /sys/fs/pstore 2>/dev/null)" ]; then
  install -d -m 0755 "$panic_dir"
  dest="$panic_dir/panic-$(date +%Y%m%dT%H%M%S)"
  mkdir -p "$dest"
  cp -r /sys/fs/pstore/* "$dest/"
  chmod -R 0644 "$dest"/*
  echo "Captured $(ls /sys/fs/pstore | wc -l) pstore entries to $dest"
  # Clean pstore to free the reserved RAM region for next panic
  for f in /sys/fs/pstore/*; do
    : > "$f" 2>/dev/null || true
  done
fi
