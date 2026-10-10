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
              pkgs.nodejs_22
              pkgs.gnutar
              pkgs.gzip
            ];
          }
          ''
            export HOME="$TMPDIR/home"
            mkdir -p "$TMPDIR/bin"
            cat > "$TMPDIR/bin/npm" <<'SH'
            #!${pkgs.bash}/bin/bash
            case "$HOME" in
              */missing) : ;;
              */directory) mkdir "$3/fixture" ;;
              */dangling) ln -s /missing "$3/fixture" ;;
              */escape) ln -s "$TMPDIR/outside" "$3/fixture" ;;
            esac
            SH
            chmod +x "$TMPDIR/bin/npm"
            printf fixture > "$TMPDIR/outside"
            mkdir "$TMPDIR/package"
            cat > "$TMPDIR/package/package.json" <<'JSON'
            {"name":"@fixture/neutral","version":"1.0.0","bin":{"fixture":"fixture"}}
            JSON
            cat > "$TMPDIR/package/npm-shrinkwrap.json" <<'JSON'
            {"name":"@fixture/neutral","version":"1.0.0","lockfileVersion":3,"packages":{"":{"name":"@fixture/neutral","version":"1.0.0"}}}
            JSON
            tar -czf "$TMPDIR/package.tgz" -C "$TMPDIR" package
            runtime="$TMPDIR/bin:$PATH"
            for kind in missing directory dangling escape; do
              export HOME="$TMPDIR/home/$kind"
              state="$HOME/.local/state/$kind/npm/bin"
              mkdir -p "$state"
              case "$kind" in
                directory) mkdir "$state/fixture" ;;
                dangling) ln -s /missing "$state/fixture" ;;
              esac
              if ${pkgs.bash}/bin/bash ${../../scripts/sinnix-agent-npm-bootstrap} "$kind" @fixture/neutral fixture "$runtime" "$TMPDIR/package.tgz" >"$TMPDIR/$kind.out" 2>"$TMPDIR/$kind.err"; then
                echo "accepted unusable binary: $kind" >&2
                exit 1
              fi
              test ! -e "$HOME/.local/state/$kind/npm/lib/node_modules/@fixture/neutral"
            done
            echo 'Unusable recovery outputs rejected in all four cases'
            touch "$out"
          '';
    };
}
