#!/usr/bin/env bash

set -euo pipefail

helper="${1:?kitty-focus-opacity script path required}"
test_root="$(mktemp -d)"
trap 'rm -rf "$test_root"' EXIT

mkdir -p "$test_root/bin" "$test_root/runtime"
touch "$test_root/runtime/kitty-test-41" "$test_root/runtime/kitty-test-42"

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
      printf '%s\n' '[{"id":5,"is_focused":false,"tabs":[{"windows":[{"id":5,"title":"same","is_focused":false}]}]}]'
      ;;
    *kitty-test-42)
      if [[ "${KITTY_TEST_FOCUS:-focused}" == focused ]]; then
        printf '%s\n' '[{"id":16,"is_focused":true,"tabs":[{"windows":[{"id":16,"title":"same","is_focused":true},{"id":3,"title":"same","is_focused":false}]}]},{"id":19,"is_focused":false,"tabs":[{"windows":[{"id":7,"title":"same","is_focused":false}]}]}]'
      else
        printf '%s\n' '[{"id":16,"is_focused":false,"tabs":[{"windows":[{"id":16,"title":"same","is_focused":false},{"id":3,"title":"same","is_focused":false}]}]},{"id":19,"is_focused":false,"tabs":[{"windows":[{"id":7,"title":"same","is_focused":false}]}]}]'
      fi
      ;;
  esac
else
  printf '%s\n' "$*" >>"$KITTY_TEST_LOG"
fi
EOF

chmod +x "$test_root/bin/kitty"
sed -i "1c#!$(command -v bash)" "$test_root/bin/kitty"

run_once() {
  env \
    USER=test \
    KITTY_TEST_LOG="$test_root/kitty.log" \
    KITTY_OPACITY_RUNTIME_DIR="$test_root/runtime" \
    KITTY_BIN="$test_root/bin/kitty" \
    "$helper" --once
}

run_once

expected="$test_root/expected.log"
cat >"$expected" <<EOF
@ --to unix:$test_root/runtime/kitty-test-42 set-background-opacity --match id:16 0.90
@ --to unix:$test_root/runtime/kitty-test-41 set-background-opacity --all 0.70
@ --to unix:$test_root/runtime/kitty-test-42 set-background-opacity --match not id:16 0.70
EOF

diff -u "$expected" "$test_root/kitty.log"

: >"$test_root/kitty.log"
KITTY_TEST_FOCUS=none run_once

cat >"$expected" <<EOF
@ --to unix:$test_root/runtime/kitty-test-41 set-background-opacity --all 0.70
@ --to unix:$test_root/runtime/kitty-test-42 set-background-opacity --all 0.70
EOF

diff -u "$expected" "$test_root/kitty.log"

: >"$test_root/kitty.log"
KITTY_TEST_FOCUS=none run_once
diff -u "$expected" "$test_root/kitty.log"
