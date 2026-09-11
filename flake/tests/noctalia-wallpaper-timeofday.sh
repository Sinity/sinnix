#!/usr/bin/env bash

set -euo pipefail

script="$(realpath -e "${1:?time-of-day script required}")"
work_root="$(mktemp -d)"
trap 'rm -rf "$work_root"' EXIT

mkdir -p "$work_root/bin"
{
  printf '#!%s\n' "$BASH"
  cat <<'EOF'
printf '%s\n' "${NOCTALIA_TEST_HOUR:-12}"
EOF
} >"$work_root/bin/date"
{
  printf '#!%s\n' "$BASH"
  cat <<'EOF'
set -euo pipefail
printf '%s\n' "$*" >> "$NOCTALIA_TEST_LOG"
if [[ "${1:-}" == msg && "${2:-}" == wallpaper-automation-get ]]; then
  case "${NOCTALIA_TEST_AUTOMATION:-true}" in
    true|false) printf '%s\n' "$NOCTALIA_TEST_AUTOMATION" ;;
    unavailable) exit 1 ;;
  esac
fi
EOF
} >"$work_root/noctalia"
chmod +x "$work_root/bin/date" "$work_root/noctalia"

make_fixture() {
  local root="$1"
  mkdir -p "$root/home/wallpaper" "$root/original-dark" "$root/original-light"
  : >"$root/original-dark/old.jpg"
  : >"$root/original-light/old.jpg"
  ln -s "$root/original-dark" "$root/home/wallpaper/dark"
  ln -s "$root/original-light" "$root/home/wallpaper/light"
  for mood in night evening; do
    mkdir -p "$root/corpus/sets/$mood/dark" "$root/corpus/sets/$mood/light"
    : >"$root/corpus/sets/$mood/dark/$mood.jpg"
    : >"$root/corpus/sets/$mood/light/$mood.jpg"
  done
}

run_timeofday() {
  local root="$1" automation="$2" schedule="$3"
  NOCTALIA_TEST_LOG="$root/noctalia.log" \
    NOCTALIA_TEST_AUTOMATION="$automation" \
    HOME="$root/home" \
    PATH="$work_root/bin:$PATH" \
    SINNIX_NOCTALIA_BIN="$work_root/noctalia" \
    SINNIX_WALLPAPER_CORPUS="$root/corpus" \
    SINNIX_WALLPAPER_MOODS="night,evening" \
    SINNIX_WALLPAPER_TIME_OF_DAY_SCHEDULE="$schedule" \
    bash "$script"
}

assert_original_links() {
  local root="$1"
  [[ "$(readlink "$root/home/wallpaper/dark")" == "$root/original-dark" ]]
  [[ "$(readlink "$root/home/wallpaper/light")" == "$root/original-light" ]]
}

# A pinned wallpaper, and an unreachable owner, both leave watched targets
# exactly unchanged. This guards against a later restart resolving a pin via a
# different corpus link.
make_fixture "$work_root/pinned"
run_timeofday "$work_root/pinned" false "0:night,12:evening"
assert_original_links "$work_root/pinned"
! rg -q 'wallpaper-random' "$work_root/pinned/noctalia.log"

make_fixture "$work_root/unavailable"
run_timeofday "$work_root/unavailable" unavailable "0:night,12:evening"
assert_original_links "$work_root/unavailable"
! rg -q 'wallpaper-random' "$work_root/unavailable/noctalia.log"

# A declared schedule, rather than retired hardcoded boundaries, selects the
# mood and asks Noctalia to choose the new image only while automation is live.
make_fixture "$work_root/active"
run_timeofday "$work_root/active" true "0:night,12:evening"
[[ "$(readlink "$work_root/active/home/wallpaper/dark")" == "$work_root/active/corpus/sets/evening/dark" ]]
[[ "$(readlink "$work_root/active/home/wallpaper/light")" == "$work_root/active/corpus/sets/evening/light" ]]
rg -q '^msg wallpaper-random$' "$work_root/active/noctalia.log"
