#!/usr/bin/env bash

set -euo pipefail

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
test_root="$(mktemp -d)"
trap 'rm -rf "$test_root"' EXIT

mkdir -p "$test_root/bin" "$test_root/runtime"
touch "$test_root/runtime/kitty-test-41" "$test_root/runtime/kitty-test-42"

cat >"$test_root/bin/hyprctl" <<'EOF'
#!/usr/bin/env bash
printf '%s\n' '{"class":"kitty","pid":42,"title":"⠇ sinnix"}'
EOF

cat >"$test_root/bin/kitty" <<'EOF'
#!/usr/bin/env bash
socket=""
for ((i = 1; i <= $#; i++)); do
  if [[ "${!i}" == "--to" ]]; then
    next=$((i + 1))
    socket="${!next}"
  fi
done

if [[ "${*: -1}" == "ls" ]]; then
  case "$socket" in
    *kitty-test-41)
      printf '%s\n' '[{"id":5,"tabs":[{"windows":[{"id":5,"title":"other"}]}]}]'
      ;;
    *kitty-test-42)
      printf '%s\n' '[{"id":16,"tabs":[{"windows":[{"id":16,"title":"⠏ sinnix"}]}]},{"id":19,"tabs":[{"windows":[{"id":3,"title":"⠏ polylogue"}]}]}]'
      ;;
  esac
else
  printf '%s\n' "$*" >>"$KITTY_TEST_LOG"
fi
EOF

chmod +x "$test_root/bin/hyprctl" "$test_root/bin/kitty"

run_once() {
  env \
    USER=test \
    KITTY_TEST_LOG="$test_root/kitty.log" \
    KITTY_OPACITY_RUNTIME_DIR="$test_root/runtime" \
    HYPRCTL_BIN="$test_root/bin/hyprctl" \
    KITTY_BIN="$test_root/bin/kitty" \
    "$repo_root/scripts/kitty-focus-opacity" --once
}

run_once

expected="$test_root/expected.log"
cat >"$expected" <<EOF
@ --to unix:$test_root/runtime/kitty-test-42 set-background-opacity --match id:16 0.90
@ --to unix:$test_root/runtime/kitty-test-41 set-background-opacity --all 0.70
@ --to unix:$test_root/runtime/kitty-test-42 set-background-opacity --match not id:16 0.70
EOF

diff -u "$expected" "$test_root/kitty.log"

cat >"$test_root/bin/hyprctl" <<'EOF'
#!/usr/bin/env bash
printf '%s\n' '{"class":"google-chrome","pid":99,"title":"browser"}'
EOF

: >"$test_root/kitty.log"
run_once

cat >"$expected" <<EOF
@ --to unix:$test_root/runtime/kitty-test-41 set-background-opacity --all 0.70
@ --to unix:$test_root/runtime/kitty-test-42 set-background-opacity --all 0.70
EOF

diff -u "$expected" "$test_root/kitty.log"

cat >"$test_root/bin/hyprctl" <<'EOF'
#!/usr/bin/env bash
printf '%s\n' '{"class":"kitty","pid":42,"title":"missing"}'
EOF

: >"$test_root/kitty.log"
run_once
diff -u "$expected" "$test_root/kitty.log"
