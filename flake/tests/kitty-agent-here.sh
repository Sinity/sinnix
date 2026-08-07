#!/usr/bin/env bash

set -euo pipefail

helper="$1"
test_root="$(mktemp -d)"
trap 'rm -rf "$test_root"' EXIT

mkdir -p "$test_root/bin" "$test_root/runtime" "$test_root/proc/100" "$test_root/proc/200" "$test_root/work/lynchpin" "$test_root/work/sinnix"
python3 -c 'import socket, sys; s = socket.socket(socket.AF_UNIX); s.bind(sys.argv[1])' "$test_root/runtime/kitty-test-100"
{
  printf 'kitty (kitty)'
  printf ' 0%.0s' {1..19}
  printf ' 100\n'
} >"$test_root/proc/100/stat"
{
  printf 'shell (shell)'
  printf ' 0%.0s' {1..19}
  printf ' 200\n'
} >"$test_root/proc/200/stat"

cat >"$test_root/bin/hyprctl" <<'EOF'
#!/usr/bin/env bash
if [[ "${HYPR_TEST_CLASS:-kitty}" == kitty ]]; then
  printf '%s\n' '{"class":"kitty","pid":100}'
else
  printf '%s\n' '{"class":"qutebrowser","pid":300}'
fi
EOF

cat >"$test_root/bin/kitty" <<'EOF'
#!/usr/bin/env bash
socket=""
for ((i = 1; i <= $#; i++)); do
  if [[ "${!i}" == --to ]]; then
    next=$((i + 1))
    socket="${!next}"
  fi
done
if [[ "${*: -1}" == ls ]]; then
  cwd="${KITTY_TEST_CWD:-/realm/project/sinnix/work/lynchpin}"
  printf '%s\n' "[{\"id\":1,\"is_focused\":false,\"tabs\":[{\"is_focused\":false,\"windows\":[{\"is_focused\":true,\"title\":\"same\",\"foreground_processes\":[{\"pid\":200,\"cwd\":\"$cwd\"}]}]}]},{\"id\":2,\"is_focused\":true,\"tabs\":[{\"is_focused\":true,\"windows\":[{\"is_focused\":true,\"title\":\"same\",\"foreground_processes\":[{\"pid\":200,\"cwd\":\"$cwd\"}]}]}]}]"
else
  printf '%s\n' "$*" >>"$KITTY_TEST_LOG"
fi
EOF

cat >"$test_root/bin/ps" <<'EOF'
#!/usr/bin/env bash
if [[ "${*: -1}" == 200 ]]; then
  printf ' 100\n'
else
  printf ' 1\n'
fi
EOF

cat >"$test_root/bin/readlink" <<'EOF'
#!/usr/bin/env bash
printf '%s\n' "${KITTY_TEST_CWD:-/realm/project/sinnix/work/lynchpin}"
EOF

cat >"$test_root/bin/notify-send" <<'EOF'
#!/usr/bin/env bash
printf 'notify %s\n' "$*" >>"$KITTY_TEST_LOG"
EOF

cat >"$test_root/bin/uwsm" <<'EOF'
#!/usr/bin/env bash
printf 'fallback %s\n' "$*" >>"$KITTY_TEST_LOG"
EOF

chmod +x "$test_root/bin"/*
for fixture in "$test_root/bin"/*; do
  sed -i "1c#!$(command -v bash)" "$fixture"
done

run_helper() {
  env PATH="$test_root/bin:$PATH" USER=test XDG_RUNTIME_DIR="$test_root/runtime" SINNIX_KITTY_PROC_ROOT="$test_root/proc" SINNIX_PROJECT_ROOT="$test_root/work/sinnix" HOME="$test_root/home" KITTY_TEST_LOG="$test_root/kitty.log" KITTY_TEST_CWD="$1" "$helper" launch-agent-here --agent codex
}

run_helper "$test_root/work/lynchpin"
grep -F -- '--cwd '"$test_root/work/lynchpin"' --keep-focus' "$test_root/kitty.log"
grep -F -- "$test_root/home/.local/bin/codex" "$test_root/kitty.log"

: >"$test_root/kitty.log"
run_helper "$test_root/work/sinnix"
grep -F -- '--cwd '"$test_root/work/sinnix"' --keep-focus' "$test_root/kitty.log"

: >"$test_root/kitty.log"
HYPR_TEST_CLASS=browser run_helper "$test_root/work/lynchpin"
sleep 0.1
grep -F -- 'fallback app -- kitty --directory '"$test_root/work/sinnix" "$test_root/kitty.log"
grep -F -- 'notify ' "$test_root/kitty.log"

: >"$test_root/kitty.log"
rm "$test_root/proc/200/stat"
run_helper "$test_root/work/lynchpin"
sleep 0.1
grep -F -- 'fallback app -- kitty --directory '"$test_root/work/sinnix" "$test_root/kitty.log"
