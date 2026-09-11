#!/usr/bin/env bash

set -euo pipefail

source_root="$(realpath -e "${1:?pinned Noctalia source required}")"
automation_patch="$(realpath -e "${2:?automation patch required}")"
audio_patch="$(realpath -e "${3:?audio patch required}")"
wallpaper_script="$(realpath -e "${4:?wallpaper script required}")"
timeofday_script="$(realpath -e "${5:?time-of-day script required}")"
timeofday_contract="$(realpath -e "${6:?time-of-day behavior test required}")"

work_root="$(mktemp -d)"
trap 'rm -rf "$work_root"' EXIT

cp -a "$source_root/." "$work_root"
chmod -R u+w "$work_root"
git -C "$work_root" init -q
git -C "$work_root" apply --check "$automation_patch"
(
  cd "$work_root"
  patch -p1 --dry-run < "$audio_patch"
)

bash -n "$wallpaper_script" "$timeofday_script"
bash "$timeofday_contract" "$timeofday_script"
! rg -q '(^|[^[:alnum:]_])(awk|mv)[[:space:]].*config\.toml' "$wallpaper_script"
! rg -q 'settings\.toml|repoint_state' "$timeofday_script"
rg -q 'wallpaper-automation-set' "$wallpaper_script"
rg -q 'wallpaper-automation-get' "$timeofday_script"
