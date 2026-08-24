#!/usr/bin/env bash
set -euo pipefail
umask 0077
usage() { printf 'usage: %s --repo PATH --out DIR [--conflict FILE ...]\n' "$0" >&2; }
repo=
out=
conflicts=()
while [[ $# -gt 0 ]]; do
  case $1 in
  --repo)
    repo=$2
    shift 2
    ;;
  --out)
    out=$2
    shift 2
    ;;
  --conflict)
    conflicts+=("$2")
    shift 2
    ;;
  -h | --help)
    usage
    exit 0
    ;;
  *)
    usage
    exit 64
    ;;
  esac
done
[[ -n $repo && -n $out ]] || {
  usage
  exit 64
}
repo=$(git -C "$repo" rev-parse --show-toplevel)
[[ $out == /* ]] || {
  echo 'output must be absolute' >&2
  exit 64
}
mkdir -p "$out/conflicts"
git -C "$repo" status --short >"$out/status.txt"
git -C "$repo" reflog -n 100 >"$out/reflog.txt"
git -C "$repo" diff --binary >"$out/diff.patch"
git -C "$repo" diff --cached --binary >"$out/cached.patch"
hashes=()
index=0
for file in "${conflicts[@]}"; do
  [[ -f $file ]] || {
    echo "conflict file is not regular: $file" >&2
    exit 1
  }
  target="$out/conflicts/$index-$(basename "$file")"
  cp -- "$file" "$target"
  hashes+=("$(sha256sum "$target")")
  index=$((index + 1))
done
manifest_tmp=$(mktemp "$out/.manifest.XXXXXX")
jq -n \
  --arg timestamp "$(date -u +%Y-%m-%dT%H:%M:%SZ)" \
  --arg repo "$repo" \
  --arg branch "$(git -C "$repo" symbolic-ref --short -q HEAD || echo DETACHED)" \
  --arg head "$(git -C "$repo" rev-parse HEAD)" \
  --argjson conflicts "$(printf '%s\n' "${hashes[@]}" | jq -Rsc 'split("\n") | map(select(length > 0))')" \
  '{schema_version:1, timestamp:$timestamp, repo:$repo, branch:$branch, head:$head, artifacts:["status.txt","reflog.txt","diff.patch","cached.patch"], conflict_hashes:$conflicts}' >"$manifest_tmp"
chmod 0600 "$manifest_tmp"
mv -- "$manifest_tmp" "$out/manifest.json"
printf '%s\n' "$out"
