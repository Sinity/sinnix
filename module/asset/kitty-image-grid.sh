#!/usr/bin/env bash
set -euo pipefail

if [[ -z "${KITTY_WINDOW_ID:-}" ]]; then
  printf 'kitty-image-grid: run inside kitty (KITTY_WINDOW_ID missing)\n' >&2
  exit 1
fi

cols=3
rows=0
tile_w=40
tile_h=22
clear_first=1
loop_anim=1

usage() {
  printf '%s\n' \
    "kitty-image-grid - place a tiled preview wall in the current kitty window" \
    "" \
    "Usage: kitty-image-grid [options] [FILES...]" \
    "" \
    "Options:" \
    "  --cols N          number of columns (default: 3)" \
    "  --rows N          number of rows to draw (default: auto)" \
    "  --tile-width N    tile width in terminal cells (default: 40)" \
    "  --tile-height N   tile height in terminal cells (default: 22)" \
    "  --no-clear        do not clear previous graphics before drawing" \
    "  --no-loop         disable looping for animated formats" \
    "  --help            display this help and exit" \
    "" \
    "If FILES are omitted, images in the current directory are used (sorted)."
}

args=()
while [[ $# -gt 0 ]]; do
  case "$1" in
    --cols)
      cols="$2"
      shift 2
      ;;
    --rows)
      rows="$2"
      shift 2
      ;;
    --tile-width)
      tile_w="$2"
      shift 2
      ;;
    --tile-height)
      tile_h="$2"
      shift 2
      ;;
    --no-clear)
      clear_first=0
      shift
      ;;
    --no-loop)
      loop_anim=0
      shift
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    --)
      shift
      args+=("$@")
      break
      ;;
    -*)
      printf 'kitty-image-grid: unknown option %s\n' "$1" >&2
      usage >&2
      exit 2
      ;;
    *)
      args+=("$1")
      shift
      ;;
  esac
done

if [[ -z "$cols" || "$cols" -le 0 ]]; then
  printf 'kitty-image-grid: --cols must be positive\n' >&2
  exit 2
fi

if [[ -z "$tile_w" || "$tile_w" -le 0 || -z "$tile_h" || "$tile_h" -le 0 ]]; then
  printf 'kitty-image-grid: tile dimensions must be positive\n' >&2
  exit 2
fi

if [[ ${#args[@]} -eq 0 ]]; then
  list_tmp=$(mktemp "kitty-grid.XXXXXX")
  python3 -c "
from pathlib import Path

EXTS = {
    '.png',
    '.jpg',
    '.jpeg',
    '.gif',
    '.webp',
    '.avif',
    '.heif',
    '.heic',
    '.jxl',
}

paths = [
    str(p)
    for p in Path.cwd().iterdir()
    if p.is_file() and p.suffix.lower() in EXTS
]

for item in sorted(paths):
    print(item)
" >"$list_tmp"
  mapfile -t args <"$list_tmp"
  rm -f "$list_tmp"
fi

if [[ ${#args[@]} -eq 0 ]]; then
  printf 'kitty-image-grid: nothing to display\n' >&2
  exit 0
fi

if (( clear_first == 1 )); then
  kitty +kitten icat --clear || true
fi

col=0
row=0
tiles_drawn=0

place_image() {
  local file="$1"
  local x=$(( col * tile_w ))
  local y=$(( row * tile_h ))
  local extra=()

  if (( loop_anim == 1 )); then
    local mime
    mime=$(file --mime-type -b -- "$file" 2>/dev/null || true)
    case "$mime" in
      image/gif|image/apng|image/webp)
        extra+=(--loop -1)
        ;;
    esac
  fi

  local geometry
  printf -v geometry '%sx%s@%sx%s' "$tile_w" "$tile_h" "$x" "$y"
  local cmd=(
    kitty +kitten icat
    --transfer-mode=stream
    --place "$geometry"
  )
  if ((${#extra[@]})); then
    cmd+=("${extra[@]}")
  fi
  cmd+=(-- "$file")
  "${cmd[@]}"
}

for file in "${args[@]}"; do
  if [[ ! -f "$file" ]]; then
    continue
  fi

  place_image "$file"

  col=$((col + 1))
  tiles_drawn=$((tiles_drawn + 1))

  if (( col >= cols )); then
    col=0
    row=$((row + 1))
    if (( rows > 0 && row >= rows )); then
      break
    fi
  fi
done

printf 'kitty-image-grid: drew %d tiles\n' "$tiles_drawn" >&2
