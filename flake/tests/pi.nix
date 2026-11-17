# Sinnix's own pi extensions (dots/pi), run against the pinned pi.
#
# The extensions are loaded the way pi resolves them, with pi's own packages
# as `node_modules`, and exercised through a stand-in for pi's extension API:
# the command guard against the real guard script, the question tool, the
# presets, and the comparison loop against the packaged ranking command in a
# scratch root. What this cannot show is pi's terminal rendering or a model
# calling the tools.
{ inputs, ... }:
{
  perSystem =
    { system, sinnixScriptRegistry, ... }:
    let
      pkgs = inputs.nixpkgs.legacyPackages.${system};
      piPackage = inputs.pi.packages.${system}.pi;
    in
    {
      checks.pi-extensions =
        pkgs.runCommand "pi-extensions-check"
          {
            nativeBuildInputs = [
              pkgs.nodejs_22
              pkgs.python3
              sinnixScriptRegistry.packageSet.sinnix-rank
            ];
          }
          ''
            mkdir -p work/dots/claude rank agent
            ln -s ${piPackage}/lib/pi/node_modules work/node_modules
            cp -r ${../../dots/pi} work/dots/pi
            cp -r ${../../dots/claude/hooks} work/dots/claude/hooks
            chmod -R u+w work/dots
            # The sandbox has no /usr/bin/env for the guard's interpreter line.
            patchShebangs work/dots/claude/hooks/pretooluse-bash.py
            export SINNIX_RANK_ROOT="$PWD/rank" PI_CODING_AGENT_DIR="$PWD/agent" HOME="$PWD"
            cd work/dots/pi
            node tests/run.mjs
            node tests/run.mjs --schemas > "$TMPDIR/schemas.json"
            ${pkgs.jq}/bin/jq -e '
              ([.tools[].name] == ["ask_operator", "rank_options"]) and
              ([.presets[].name] == ["explore", "inquire", "learn", "questions"]) and
              (.commands | index("loom") != null)
            ' "$TMPDIR/schemas.json" >/dev/null
            test "$(${piPackage}/bin/pi --version)" = 1.5.2
            touch "$out"
          '';
    };
}
