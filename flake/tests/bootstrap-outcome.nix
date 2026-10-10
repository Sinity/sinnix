{ inputs, ... }:
{
  perSystem =
    { system, ... }:
    let
      pkgs = inputs.nixpkgs.legacyPackages.${system};
    in
    {
      checks.agent-bootstrap-outcome =
        pkgs.runCommand "agent-bootstrap-outcome-check"
          {
            nativeBuildInputs = [
              pkgs.bash
              pkgs.coreutils
              pkgs.util-linux
            ];
          }
          ''
            export HOME="$TMPDIR/home"
            mkdir -p "$TMPDIR/bin"
            printf '#!${pkgs.bash}/bin/bash\nexit 0\n' > "$TMPDIR/bin/npm"
            chmod +x "$TMPDIR/bin/npm"
            printf fixture > "$TMPDIR/package.tgz"
            runtime="$TMPDIR/bin:$PATH"
            for kind in missing nonexec directory dangling; do
              state="$HOME/.local/state/$kind/npm/bin"
              mkdir -p "$state"
              case "$kind" in
                nonexec) printf fixture > "$state/fixture" ;;
                directory) mkdir "$state/fixture" ;;
                dangling) ln -s /missing "$state/fixture" ;;
              esac
              if ${pkgs.bash}/bin/bash ${../../scripts/sinnix-agent-npm-bootstrap} "$kind" @fixture/neutral fixture "$runtime" "$TMPDIR/package.tgz" >"$TMPDIR/$kind.out" 2>"$TMPDIR/$kind.err"; then
                echo "accepted unusable binary: $kind" >&2
                exit 1
              fi
              grep -Fq 'did not produce an executable regular file' "$TMPDIR/$kind.err"
            done
            echo 'Unusable recovery outputs rejected in all four cases'
            touch "$out"
          '';
    };
}
