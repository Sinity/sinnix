#!/usr/bin/env bash
set -euo pipefail
usage() { printf 'usage: %s --repo PATH --missing PATH [--beads-jsonl FILE ...] [--snapshot-root DIR]\n' "$0" >&2; }
repo=
missing=
beads=()
snapshot_root=
while [[ $# -gt 0 ]]; do
  case $1 in
  --repo)
    repo=$2
    shift 2
    ;;
  --missing)
    missing=$2
    shift 2
    ;;
  --beads-jsonl)
    beads+=("$2")
    shift 2
    ;;
  --snapshot-root)
    snapshot_root=$2
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
[[ -n $repo && -n $missing ]] || {
  usage
  exit 64
}
repo=$(git -C "$repo" rev-parse --show-toplevel)
git_candidate=0
git -C "$repo" ls-files --error-unmatch -- "$missing" >/dev/null 2>&1 && git_candidate=1 || true
bead_candidates=()
for file in "${beads[@]}"; do
  [[ -f $file ]] || {
    echo "missing beads JSONL: $file" >&2
    exit 1
  }
  while IFS= read -r row; do bead_candidates+=("$row"); done < <(jq -c --arg id "$missing" 'select(.id == $id) | {id,updated_at,status}' "$file")
done
jq -n \
  --arg missing "$missing" \
  --arg repo "$repo" \
  --arg filesystem "$(if [[ -e $missing ]]; then printf present; else printf absent; fi)" \
  --argjson git_index "$git_candidate" \
  --argjson beads "$(printf '%s\n' "${bead_candidates[@]}" | jq -sc '.')" \
  --arg snapshot "$snapshot_root" \
  '{schema_version:1, missing:$missing, repo:$repo, authorities:{filesystem:$filesystem,git_index:$git_index,beads:$beads,snapshot_root:(if $snapshot=="" then null else $snapshot end)}, action:null, authorization_required:true}'
