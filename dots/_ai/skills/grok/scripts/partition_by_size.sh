#!/usr/bin/env bash
# Propose audit-region boundaries for a codebase by real measured size.
#
# Walks a directory tree, sums matching-file line counts per subdirectory,
# and prints regions at or under a target size — starting point for a `grok`
# campaign's partition, not a final answer. Sanity-check the output against
# real module boundaries before dispatching agents against it.
#
# Usage:
#   partition_by_size.sh <root-dir> <target-lines> [file-glob]
#
# Examples:
#   partition_by_size.sh crate/sinexd/src 8000 '*.rs'
#   partition_by_size.sh src 5000 '*.py'
set -euo pipefail

root=${1:?usage: partition_by_size.sh <root-dir> <target-lines> [file-glob]}
target=${2:?usage: partition_by_size.sh <root-dir> <target-lines> [file-glob]}
glob=${3:-*.rs}

if [[ ! -d $root ]]; then
  echo "error: not a directory: $root" >&2
  exit 1
fi

total_lines() {
  local dir=$1
  find "$dir" -maxdepth "${2:-999}" -name "$glob" -not -name "*_test.*" -not -name "*test_*" -print0 |
    xargs -0 -r cat 2>/dev/null | wc -l
}

echo "# Partition proposal: $root (glob=$glob, target=$target lines/region)"
echo "# format: <status> <lines> <path>"
echo "#   OK    = at/under target, treat as one region"
echo "#   SPLIT = over target, drill into its own subdirectories (rerun this"
echo "#           script pointed at the path, or split by hand along module"
echo "#           seams / pub fn boundaries for a single oversized file)"
echo

walk() {
  local dir=$1
  local lines
  lines=$(total_lines "$dir" 1) # this dir's own loose files only
  local subtotal=0
  local sub
  for sub in "$dir"/*/; do
    [[ -d $sub ]] || continue
    sub=${sub%/}
    local sub_lines
    sub_lines=$(total_lines "$sub")
    subtotal=$((subtotal + sub_lines))
    if ((sub_lines > target)); then
      echo "SPLIT $sub_lines $sub"
      walk "$sub"
    elif ((sub_lines > 0)); then
      echo "OK    $sub_lines $sub"
    fi
  done
  if ((lines > 0)); then
    echo "OK    $lines $dir (loose files only, not subdirs)"
  fi
}

walk "$root"

echo
grand_total=$(total_lines "$root")
echo "# total: $grand_total lines under $root"
