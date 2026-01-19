{ pkgs }:
pkgs.writeShellScriptBin "lsp-root" ''
  set -euo pipefail
  start_dir="''${CCLSP_START_DIR:-$PWD}"
  if [ -z "$start_dir" ]; then
    start_dir="$PWD"
  fi
  markers="''${CCLSP_ROOT_MARKERS:-Cargo.toml:go.mod:package.json:pyproject.toml:flake.nix:.git}"
  IFS=':' read -r -a marker_list <<< "$markers"
  search_dir="$start_dir"
  found_root=""
  while [ "$search_dir" != "/" ]; do
    for marker in "''${marker_list[@]}"; do
      if [ -e "$search_dir/$marker" ]; then
        found_root="$search_dir"
        break 2
      fi
    done
    search_dir="$(dirname "$search_dir")"
  done
  if [ -z "$found_root" ]; then
    found_root="$start_dir"
  fi
  cd "$found_root"
  exec "$@"
''
