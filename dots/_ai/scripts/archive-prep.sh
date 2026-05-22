#!/usr/bin/env bash
# Prepare /outer-realm/archive for Google Drive upload.
# Phase 1: encrypt remaining directories (util/, data/) into single age blobs
# Phase 2: write the staging+upload script
set -euo pipefail

AGE="/nix/store/h963yim5mc9429i628d0hnhpfvzhlxdr-age-1.3.1/bin/age"
ARCHIVE="/outer-realm/archive"
STAGED="/outer-realm/archive-staged"
GDRIVE="gdrive:archive"

echo "=== Archive → GDrive Preparation ==="
echo

# ── Remaining directories to encrypt ───────────────────────────────
# Each becomes a single tar.zst.age blob. Already-done items skipped.

encrypt_dir() {
  local dir="$1" name="$2"
  local out="$ARCHIVE/${name}.tar.zst.age"
  if [ -f "$out" ]; then
    echo "SKIP $name (already exists: $(du -h "$out" | cut -f1))"
    return 0
  fi
  echo "ENCRYPT $name ($(du -sh "$dir" | cut -f1)) → $out"
  tar cf - -C "$(dirname "$dir")" "$(basename "$dir")" |
    zstd -3 -c |
    $AGE -R ~/.ssh/id_ed25519.pub -o "$out"
  echo "  done: $(du -h "$out" | cut -f1)"
}

encrypt_dir "$ARCHIVE/util" "util"
encrypt_dir "$ARCHIVE/data" "data"
encrypt_dir "$ARCHIVE/curious-datasets" "curious-datasets"

echo
echo "=== All encryption complete ==="

# ── Stage for upload ───────────────────────────────────────────────
echo
echo "=== Staging .age files for rclone ==="
sudo mkdir -p "$STAGED"

find "$ARCHIVE" -name "*.age" -type f | while read agefile; do
  rel="${agefile#$ARCHIVE/}"
  staged="$STAGED/$rel"
  if [ ! -e "$staged" ]; then
    sudo mkdir -p "$(dirname "$staged")"
    sudo ln -sf "$agefile" "$staged"
    echo "  $rel ($(du -h "$agefile" | cut -f1))"
  fi
done

count=$(find "$STAGED" -type f -o -type l | wc -l)
total=$(du -sh "$STAGED" 2>/dev/null | cut -f1)
echo "Staged $count files, $total"

echo
echo "=== Ready to upload ==="
echo "  rclone sync $STAGED $GDRIVE --progress --transfers 4 --bwlimit 8M --links"
echo "  (or run: bash dots/_ai/scripts/archive-upload.sh)"
