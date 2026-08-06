#!/usr/bin/env bash

set -euo pipefail

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
test_root="$(mktemp -d)"
trap 'rm -rf "$test_root"' EXIT

mkdir -p "$test_root/bin" "$test_root/runtime"
touch "$test_root/runtime/kitty-test-41" "$test_root/runtime/kitty-test-42"

cat >"$test_root/bin/hyprctl" <<'EOF'
#!/usr/bin/env bash
printf '%s\n' '{"class":"kitty","pid":42}'
EOF

cat >"$test_root/bin/kitty" <<'EOF'
#!/usr/bin/env bash
printf '%s\n' "$*" >>"$KITTY_TEST_LOG"
EOF

chmod +x "$test_root/bin/hyprctl" "$test_root/bin/kitty"

env \
  USER=test \
  KITTY_TEST_LOG="$test_root/kitty.log" \
  KITTY_OPACITY_RUNTIME_DIR="$test_root/runtime" \
  HYPRCTL_BIN="$test_root/bin/hyprctl" \
  KITTY_BIN="$test_root/bin/kitty" \
  "$repo_root/scripts/kitty-focus-opacity" --once

expected="$test_root/expected.log"
cat >"$expected" <<EOF
@ --to unix:$test_root/runtime/kitty-test-41 set-background-opacity --all 0.72
@ --to unix:$test_root/runtime/kitty-test-42 set-background-opacity --all 0.72
@ --to unix:$test_root/runtime/kitty-test-42 set-background-opacity 0.96
EOF

diff -u "$expected" "$test_root/kitty.log"

cat >"$test_root/bin/hyprctl" <<'EOF'
#!/usr/bin/env bash
printf '%s\n' '{"class":"google-chrome","pid":99}'
EOF

: >"$test_root/kitty.log"
env \
  USER=test \
  KITTY_TEST_LOG="$test_root/kitty.log" \
  KITTY_OPACITY_RUNTIME_DIR="$test_root/runtime" \
  HYPRCTL_BIN="$test_root/bin/hyprctl" \
  KITTY_BIN="$test_root/bin/kitty" \
  "$repo_root/scripts/kitty-focus-opacity" --once

if [[ "$(wc -l <"$test_root/kitty.log")" -ne 2 ]]; then
  printf 'browser focus should only apply inactive opacity\n' >&2
  exit 1
fi

cat >"$test_root/bin/hyprctl" <<'EOF'
#!/usr/bin/env bash
printf '%s\n' '{"class":"kitty","pid":43}'
EOF

: >"$test_root/kitty.log"
(
  sleep 0.2
  touch "$test_root/runtime/kitty-test-43"
) &
env \
  USER=test \
  KITTY_TEST_LOG="$test_root/kitty.log" \
  KITTY_OPACITY_RUNTIME_DIR="$test_root/runtime" \
  HYPRCTL_BIN="$test_root/bin/hyprctl" \
  KITTY_BIN="$test_root/bin/kitty" \
  "$repo_root/scripts/kitty-focus-opacity" --once

grep -Fqx \
  "@ --to unix:$test_root/runtime/kitty-test-43 set-background-opacity 0.96" \
  "$test_root/kitty.log"
