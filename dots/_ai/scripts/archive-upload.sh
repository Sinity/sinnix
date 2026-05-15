#!/usr/bin/env bash
# Archive → Google Drive upload script
# Encrypted .age files are synced to gdrive:archive/ preserving directory structure.
# Run with: bash archive-upload.sh [--dry-run]
set -euo pipefail

AGE_BIN="/nix/store/h963yim5mc9429i628d0hnhpfvzhlxdr-age-1.3.1/bin/age"
ARCHIVE_ROOT="/outer-realm/archive"
STAGED_ROOT="/outer-realm/archive-staged"
GDRIVE_TARGET="gdrive:archive"

DRY_RUN=""
if [ "${1:-}" = "--dry-run" ]; then
  DRY_RUN="--dry-run"
  echo "=== DRY RUN ==="
fi

# ── Phase 1: Stage symlinks to .age files ──────────────────────────
echo "=== Staging encrypted files ==="
sudo mkdir -p "$STAGED_ROOT"

find "$ARCHIVE_ROOT" -name "*.age" -type f | while read agefile; do
  rel="${agefile#$ARCHIVE_ROOT/}"
  staged="$STAGED_ROOT/$rel"
  if [ ! -e "$staged" ]; then
    sudo mkdir -p "$(dirname "$staged")"
    sudo ln -sf "$agefile" "$staged"
    echo "  $rel"
  fi
done
echo "Staging complete"

# ── Phase 2: Sync to Google Drive ──────────────────────────────────
echo
echo "=== Uploading to $GDRIVE_TARGET ==="
rclone sync "$STAGED_ROOT" "$GDRIVE_TARGET" \
  $DRY_RUN \
  --progress \
  --transfers 4 \
  --bwlimit 8M \
  --links \
  --create-empty-src-dirs \
  --ignore-errors \
  --stats 30s \
  -v

echo
echo "=== Upload complete ==="

# ── Phase 3: Verify ────────────────────────────────────────────────
if [ -z "$DRY_RUN" ]; then
  echo
  echo "=== Verifying ==="
  rclone check "$STAGED_ROOT" "$GDRIVE_TARGET" \
    --links \
    --one-way \
    --missing-on-dst /tmp/upload_missing.txt

  if [ -s /tmp/upload_missing.txt ]; then
    echo "WARNING: Files missing on remote:"
    head -20 /tmp/upload_missing.txt
  else
    echo "All files verified on remote"
  fi
fi

echo
echo "=== Done ==="
