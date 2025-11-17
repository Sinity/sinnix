#!/usr/bin/env bash
# combine-files-batch.sh — Non-interactive bundler that groups files into
# sources, tests, and docs and emits combined markdown reports.
set -euo pipefail
IFS=$'\n\t'

ROOT=${1:-$(pwd)}
OUTPUT_DIR=${2:-combined-bundles}

# Directories to exclude entirely
EXCLUDES=(
  '.git/*'
  'target/*'
  'node_modules/*'
  'result/*'
  'dist/*'
  'build/*'
  '.venv/*'
  'venv/*'
  '.sqlx/*'
  '*.lock'
  'nixos/grafana-dashboards/*'
  'docs/test-suite-report/*'
  'docs/historical/*'
  "$OUTPUT_DIR/*"
)

mkdir -p "$OUTPUT_DIR"

is_text_file() {
  local mime
  mime=$(file --mime-type -b "$1")
  if [[ $mime == text/* ]]; then
    return 0
  fi
  case $mime in
    application/json|application/xml|application/x-yaml|application/yaml|application/x-sh|application/javascript|application/x-toml)
      return 0
      ;;
    *)
      return 1
      ;;
  esac
}

is_doc_file() {
  local path=$1
  case $path in
    */docs/*|docs/*|*/doc/*|doc/*|schemas/*|*/schemas/*)
      return 0
      ;;
  esac
  local ext=${path##*.}
  case $ext in
    md|mdx|rst|txt|adoc|org|markdown|rtf)
      return 0
      ;;
  esac
  return 1
}

is_test_file() {
  local path=$1
  case $path in
    */tests/*|tests/*|*/test/*|test/*)
      return 0
      ;;
  esac
  local base
  base=$(basename "$path")
  case $base in
    *_test.*|*_tests.*|test_*.rs|test-*.rs)
      return 0
      ;;
  esac
  return 1
}

path_priority() {
  local rel=$1
  case $rel in
    README.md|README.MD|README|AGENTS.md|CLAUDE.md|TESTING.md)
      echo 10
      return
      ;;
  esac
  case $rel in
    docs/README.md|docs/architecture/*)
      echo 12
      return
      ;;
  esac
  case $rel in
    Cargo.toml|justfile|flake.nix|flake.lock|deny.toml|clippy.toml|.pre-commit-config.yaml|.editorconfig|.gitignore|.cargo/config.toml|.cargo-machete.toml)
      echo 15
      return
      ;;
  esac
  case $rel in
    scripts/*)
      echo 20
      return
      ;;
    docs/*)
      echo 25
      return
      ;;
    cli/*)
      echo 30
      return
      ;;
    nixos/*)
      echo 40
      return
      ;;
    schemas/*)
      echo 45
      return
      ;;
    crate/lib/*)
      echo 50
      return
      ;;
    crate/core/*)
      echo 60
      return
      ;;
    crate/satellites/*)
      echo 70
      return
      ;;
    src/*)
      echo 80
      return
      ;;
    tests/*)
      echo 85
      return
      ;;
  esac
  echo 100
}

sort_array() {
  local -n arr=$1
  if ((${#arr[@]} == 0)); then
    return
  fi
  local temp=()
  for f in "${arr[@]}"; do
    local rel=${f#"$ROOT"/}
    local priority
    priority=$(path_priority "$rel")
    temp+=("$(printf '%04d' "$priority")|$rel")
  done
  local sorted=()
  while IFS= read -r entry; do
    sorted+=("$entry")
  done < <(printf '%s\n' "${temp[@]}" | sort)
  arr=()
  for entry in "${sorted[@]}"; do
    local rel_only=${entry#*|}
    if [[ "$ROOT" == "." ]]; then
      arr+=("$rel_only")
    else
      arr+=("$ROOT/$rel_only")
    fi
  done
}

collect_files() {
  local dir=$1
  local -a args=(rg --files "$dir" --hidden --follow)
  for ex in "${EXCLUDES[@]}"; do
    args+=(-g "!$ex")
  done
  "${args[@]}"
}

build_bundle() {
  local category=$1
  shift
  local files=("$@")
  if [[ ${#files[@]} -eq 0 ]]; then
    echo "Skipping $category bundle (no files)."
    return
  fi
  local outfile="$OUTPUT_DIR/combined-$category.md"
  : >"$outfile"
  local current_date total_tokens total_files
  current_date=$(date -u +"%Y-%m-%dT%H:%M:%SZ")
  total_files=${#files[@]}
  total_tokens=0
  declare -A size_map token_map
  for f in "${files[@]}"; do
    local sz tk
    sz=$(stat -c%s "$f")
    tk=$((sz / 4))
    size_map["$f"]=$sz
    token_map["$f"]=$tk
    total_tokens=$((total_tokens + tk))
  done
  {
    echo '---'
    echo "generated: $current_date"
    echo "category: $category"
    echo "base_directory: $ROOT"
    echo "file_count: $total_files"
    echo "token_estimate: $total_tokens"
    echo '---'
    echo
    echo "## Table of Contents"
    echo
    local i=1
    for f in "${files[@]}"; do
      local rel=${f#"$ROOT"/}
      echo "$i. [$rel](#${category}-file-$i)"
      ((i++))
    done
    echo
  } >>"$outfile"

  local idx=1
  for f in "${files[@]}"; do
    local rel=${f#"$ROOT"/}
    local sz=${size_map["$f"]}
    local tk=${token_map["$f"]}
    local typ
    typ=$(file -b "$f" | cut -d, -f1)
    local ext=${f##*.}
    local lang=""
    case $ext in
      rs) lang=rust ;;
      ts) lang=typescript ;;
      js) lang=javascript ;;
      py) lang=python ;;
      sh) lang=bash ;;
      nix) lang=nix ;;
      toml) lang=toml ;;
      json) lang=json ;;
      yml|yaml) lang=yaml ;;
      md|mdx) lang=markdown ;;
    esac
    {
      echo "<a id=\"${category}-file-$idx\"></a>"
      echo "## File: $rel"
      echo
      echo "- Size: $sz bytes"
      echo "- Tokens: $tk"
      echo "- Type: $typ"
      echo
      echo '```'"$lang"
      cat "$f"
      echo '```'
      echo
    } >>"$outfile"
    ((idx++))
  done
  echo "Wrote $outfile (${total_files} files)."
}

main() {
  mapfile -t files < <(collect_files "$ROOT")
  if [[ ${#files[@]} -eq 0 ]]; then
    echo "No files found in $ROOT"
    exit 1
  fi
  declare -a sources_files=()
  declare -a tests_files=()
  declare -a docs_files=()
  for f in "${files[@]}"; do
    [[ -f $f ]] || continue
    if [[ $f == */.sqlx/* ]]; then
      continue
    fi
    if ! is_text_file "$f"; then
      continue
    fi
    if is_doc_file "$f"; then
      docs_files+=("$f")
    elif is_test_file "$f"; then
      tests_files+=("$f")
    else
      sources_files+=("$f")
    fi
  done
  sort_array sources_files
  sort_array tests_files
  sort_array docs_files
  build_bundle sources "${sources_files[@]}"
  build_bundle tests "${tests_files[@]}"
  build_bundle docs "${docs_files[@]}"
}

main "$@"
