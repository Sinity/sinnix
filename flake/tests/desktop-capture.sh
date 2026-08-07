#!/usr/bin/env bash
set -euo pipefail

ocr_helper=$1
dismiss_helper=$2
fixture_bin=$TMPDIR/bin
mkdir -p "$fixture_bin"

cat >"$fixture_bin/slurp" <<'EOF'
#!/usr/bin/env bash
printf '10,20 100x50\n'
EOF
cat >"$fixture_bin/grim" <<'EOF'
#!/usr/bin/env bash
set -euo pipefail
[ "$1" = "-g" ]
[ "$2" = "10,20 100x50" ]
printf 'fixture-image' > "$3"
EOF
cat >"$fixture_bin/tesseract" <<'EOF'
#!/usr/bin/env bash
set -euo pipefail
[ "$2" = "stdout" ]
printf 'fixture OCR text\n'
EOF
cat >"$fixture_bin/wl-copy" <<'EOF'
#!/usr/bin/env bash
cat > "$OCR_CLIPBOARD"
EOF
cat >"$fixture_bin/hyprctl" <<'EOF'
#!/usr/bin/env bash
set -euo pipefail
case "$*" in
  "-j workspaces") printf '%s\n' '[{"name":"special:scratch_term","visible":true},{"name":"special:scratch_rawlog","visible":false},{"name":"1","visible":true}]' ;;
  "dispatch togglespecialworkspace scratch_term") printf 'hidden scratch_term\n' >> "$HYPR_ACTIONS" ;;
  *) echo "unexpected hyprctl call: $*" >&2; exit 1 ;;
esac
EOF
chmod +x "$fixture_bin"/*
for fixture in "$fixture_bin"/*; do
  sed -i "1c#!$(command -v bash)" "$fixture"
done

export OCR_CLIPBOARD=$TMPDIR/clipboard
PATH="$fixture_bin:$PATH" "$ocr_helper"
[ "$(cat "$OCR_CLIPBOARD")" = "fixture OCR text" ]

export HYPR_ACTIONS=$TMPDIR/actions
PATH="$fixture_bin:$PATH" "$dismiss_helper"
[ "$(cat "$HYPR_ACTIONS")" = "hidden scratch_term" ]
