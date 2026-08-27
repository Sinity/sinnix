#!/usr/bin/env bash
# Provably fails when: the OCR helper acts on a cancelled (empty) selection,
# or the scratchpad dismisser toggles workspaces that are not visible.
set -euo pipefail

ocr_helper=$1
dismiss_helper=$2
toggle_helper=$3
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
  "-j monitors")
    special=""
    [ -s "${HYPR_SPECIAL_STATE:-/nonexistent}" ] && special=$(cat "$HYPR_SPECIAL_STATE")
    printf '[{"focused":true,"width":1920,"height":1080,"specialWorkspace":{"name":"%s"}}]\n' "$special"
    ;;
  "-j clients")
    printf '%s\n' '[{"address":"0xabc","class":"rawlog-capture","at":[100,100],"size":[900,500]}]'
    ;;
  "eval hl.dispatch(hl.dsp.workspace.toggle_special(\"scratch_term\"))")
    printf 'hidden scratch_term\n' >> "$HYPR_ACTIONS"
    ;;
  "eval hl.dispatch(hl.dsp.workspace.toggle_special(\"scratch_rawlog\"))")
    if [ "$(cat "$HYPR_SPECIAL_STATE" 2>/dev/null || true)" = "special:scratch_rawlog" ]; then
      : > "$HYPR_SPECIAL_STATE"
    else
      printf 'special:scratch_rawlog' > "$HYPR_SPECIAL_STATE"
    fi
    ;;
  "eval "*) ;;
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

# A cancelled selection must stop there: without the empty-geometry guard,
# grim is asked to capture "" and the OCR helper would clobber the clipboard
# with whatever that produced.
cat >"$fixture_bin/slurp" <<EOF
#!$(command -v bash)
printf ''
EOF
chmod +x "$fixture_bin/slurp"
rm -f "$OCR_CLIPBOARD"
PATH="$fixture_bin:$PATH" "$ocr_helper"
[ ! -e "$OCR_CLIPBOARD" ]

export HYPR_ACTIONS=$TMPDIR/actions
export HYPR_SPECIAL_STATE=$TMPDIR/special-state
printf 'special:scratch_term' > "$HYPR_SPECIAL_STATE"
PATH="$fixture_bin:$PATH" "$dismiss_helper"
[ "$(cat "$HYPR_ACTIONS")" = "hidden scratch_term" ]

config_dir=$TMPDIR/scratchpads
mkdir -p "$config_dir"
cat > "$config_dir/rawlog.conf" <<'EOF'
COMMAND=(false)
CLASS="rawlog-capture"
WORKSPACE="scratch_rawlog"
WIDTH_RATIO=0.72
HEIGHT_RATIO=0.48
EOF
: > "$HYPR_SPECIAL_STATE"
SCRATCHPAD_CONFIG_DIR="$config_dir" PATH="$fixture_bin:$PATH" "$toggle_helper" rawlog
[ "$(cat "$HYPR_SPECIAL_STATE")" = "special:scratch_rawlog" ]
SCRATCHPAD_CONFIG_DIR="$config_dir" PATH="$fixture_bin:$PATH" "$toggle_helper" rawlog
[ ! -s "$HYPR_SPECIAL_STATE" ]
