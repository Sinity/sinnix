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
            notificationRules = lib.filter (
              rule: lib.attrByPath [ "match" "namespace" ] null rule == "noctalia-notification"
            ) settings.layer_rule;
            notificationRule =
              if builtins.length notificationRules == 1 then builtins.head notificationRules else { };
          in
          [
            {
              assertion = settings.config.decoration.blur.enabled;
              message = "Global Hyprland blur must remain enabled outside the notification layer.";
            }
            {
              assertion = builtins.length notificationRules == 1;
              message = "Exactly one layer rule must target the Noctalia notification namespace.";
            }
            {
              assertion = notificationRule.blur or null == false;
              message = "The Noctalia notification layer must explicitly disable blur.";
            }
            {
              assertion = !(notificationRule ? ignore_alpha);
              message = "The notification policy must not retain ignore_alpha as a claimed blur fix.";
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
          notificationLayerRules = lib.filter (
            rule: lib.attrByPath [ "match" "namespace" ] null rule == "noctalia-notification"
          ) settings.layer_rule;
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
