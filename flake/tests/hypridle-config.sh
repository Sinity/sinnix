#!/usr/bin/env bash

set -euo pipefail

config_file="${1:-$HOME/.config/hypr/hypridle.conf}"
test -r "$config_file"

python3 - "$config_file" <<'PY'
import re
import sys

text = open(sys.argv[1], encoding="utf-8").read()
assert re.search(r"timeout\s*=\s*420", text)
assert re.search(r"timeout\s*=\s*1500", text)
assert re.search(r"on-timeout\s*=\s*hyprctl dispatch dpms off", text)
assert re.search(r"on-timeout\s*=\s*noctalia msg session lock", text)
assert re.search(r"on-resume\s*=\s*hyprctl dispatch dpms on", text)
assert "dim" not in text.lower()

timeouts = [int(value) for value in re.findall(r"timeout\s*=\s*(\d+)", text)]
assert timeouts == sorted(timeouts) and timeouts == [420, 1500]
PY

printf '%s\n' "hypridle stages: DPMS 420s, lock 1500s, no dimming"
