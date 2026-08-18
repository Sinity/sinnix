# Shell lint/syntax gate for the "second shell estate": dots/_ai/skills
# scripts, dots/claude/hooks, dots/qutebrowser/userscripts, dots/taskwarrior,
# dots/zsh -- none of which the packaged-scripts shellcheck pass in `lint`
# (flake/command-registry.nix, which only walks `scripts/`) ever touches.
# dots/claude/hooks already gets shellcheck+bash -n via hooks-harness.sh
# (flake/tests/agent-tools.nix); this check re-covers it for free by scanning
# all of dots/ uniformly, so there is one gate instead of a per-directory
# patchwork.
#
# Scope: every *.sh under dots/, plus extensionless files whose shebang names
# bash (the qutebrowser userscripts), get `shellcheck -S warning` + `bash -n`.
# Every *.zsh gets `zsh -n` (zsh is already a transitive nixpkgs dependency
# here, so the syntax check is effectively free).
#
# Mutation proof this check can actually fail: appending an unused local
# (`local desc tags project unused; unused=$(true)`) to
# dots/taskwarrior/shell-aliases.sh's twork() and building
# `.#checks.x86_64-linux.dots-shell` failed on
# `SC2034 (warning): unused appears unused` before the line was reverted.
{ inputs, ... }:
{
  perSystem =
    { system, ... }:
    let
      pkgs = inputs.nixpkgs.legacyPackages.${system};
    in
    {
      checks.dots-shell =
        pkgs.runCommand "dots-shell-check"
          {
            dotsSrc = ../../dots;
            nativeBuildInputs = [
              pkgs.bash
              pkgs.zsh
              pkgs.shellcheck
              pkgs.findutils
              pkgs.gnugrep
              pkgs.coreutils
            ];
          }
          ''
            set -euo pipefail
            dots="$TMPDIR/dots"
            cp -r "$dotsSrc" "$dots"

            mapfile -t sh_files < <(find "$dots" -name '*.sh' | sort)
            mapfile -t candidates < <(find "$dots" -type f ! -name '*.sh' ! -name '*.zsh' | sort)
            bash_files=()
            for f in "''${candidates[@]}"; do
              if head -1 "$f" 2>/dev/null | grep -qE '^#!.*\bbash\b'; then
                bash_files+=("$f")
              fi
            done
            all_bash=("''${sh_files[@]}" "''${bash_files[@]}")

            echo "shellcheck + bash -n over ''${#all_bash[@]} scripts"
            shellcheck -S warning "''${all_bash[@]}"
            for f in "''${all_bash[@]}"; do
              bash -n "$f"
            done

            mapfile -t zsh_files < <(find "$dots" -name '*.zsh' | sort)
            echo "zsh -n over ''${#zsh_files[@]} scripts"
            for f in "''${zsh_files[@]}"; do
              zsh -n "$f"
            done

            touch "$out"
          '';
    };
}
