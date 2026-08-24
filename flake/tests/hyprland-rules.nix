# Generated semantic and parser contract for Sinnix's Hyprland Lua rules.
{ inputs, ... }:
let
  inherit (inputs.nixpkgs) lib;
in
{
  perSystem =
    { system, ... }:
    let
      pkgs = inputs.nixpkgs.legacyPackages.${system};
      testLib = import ../test-lib.nix { inherit inputs lib; };
      inherit (testLib)
        baseTestConfig
        evalTestSpec
        hmFor
        mkHmRuntimeCheck
        mountTmpfsRoots
        ;
      spec = {
        name = "hyprland-rules";
        modules = [
          mountTmpfsRoots
          baseTestConfig
          ({ ... }: {
            sinnix.machine.isDesktop = true;
          })
        ];
        assertions =
          config:
          let
            settings = (hmFor config).wayland.windowManager.hyprland.settings;
          in
          [
            {
              assertion = !settings.config.decoration.blur.enabled;
              message = "Global Hyprland blur must remain disabled while Noctalia uses a full-height notification surface.";
            }
          ];
      };
      evaluated = evalTestSpec system spec;
      hyprland = evaluated.config.programs.hyprland.package;
      settings = (hmFor evaluated.config).wayland.windowManager.hyprland.settings;
    in
    {
      checks.hyprland-rules = pkgs.runCommand "sinnix-hyprland-rules" { } ''
        cat > "$out" <<'EOF_CONTRACT'
        ${builtins.toJSON {
          globalBlur = settings.config.decoration.blur.enabled;
        }}
        EOF_CONTRACT
      '';

      checks.hyprland-lua-config = mkHmRuntimeCheck system {
        name = "hyprland-lua-config";
        inherit spec;
        nativeBuildInputs = [ hyprland ];
        xdgConfigFiles = [
          "hypr/hyprland.lua"
          "hypr/sinnix-startup.lua"
        ];
        script = ''
          export XDG_RUNTIME_DIR="$TMPDIR/runtime"
          mkdir -m 700 -p "$XDG_RUNTIME_DIR"
          Hyprland --verify-config --config "$XDG_CONFIG_HOME/hypr/hyprland.lua"
        '';
      };
    };
}
