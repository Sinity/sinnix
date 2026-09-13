# Small, synthetic activity-runtime and native-plugin callback contract.
{ inputs, ... }:
{
  perSystem =
    { system, ... }:
    let
      pkgs = inputs.nixpkgs.legacyPackages.${system};
      source = pkgs.lib.fileset.toSource {
        root = ../..;
        fileset = pkgs.lib.fileset.unions [
          ../../scripts/sinnix-activity
          ./test_activity_runtime.py
          ./test_activity_desktop.py
          ../../dots/noctalia/plugins/sinnix-cockpit
          ../../dots/noctalia/config.toml
          ../../modules/features/desktop/hyprland/bindings.nix
        ];
      };
    in
    {
      checks.activity-substrate =
        pkgs.runCommand "activity-substrate-check"
          {
            nativeBuildInputs = [
              pkgs.python3
              pkgs.luau
            ];
          }
          ''
            export PYTHONDONTWRITEBYTECODE=1
            export PYTHONTZPATH=${pkgs.tzdata}/share/zoneinfo
            export LUAU_BIN=${pkgs.luau}/bin/luau
            cd ${source}
            python3 -m unittest -v flake.tests.test_activity_runtime flake.tests.test_activity_desktop
            for file in dots/noctalia/plugins/sinnix-cockpit/activity*.luau dots/noctalia/plugins/sinnix-cockpit/capture-panel.luau; do
              luau-compile "$file" >/dev/null
            done
            touch "$out"
          '';
    };
}
