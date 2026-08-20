# Focused static contract for the Hyprland 0.56 Lua migration.
{ inputs, ... }:
{
  perSystem =
    { system, ... }:
    let
      pkgs = inputs.nixpkgs.legacyPackages.${system};
    in
    {
      checks.hyprland-lua = pkgs.runCommand "hyprland-lua-check" { } ''
        set -euo pipefail

        # The compositor has one Lua authority. These paths and the legacy
        # renderer must not return through a comment, include, or watcher.
        if grep -REn 'configType = "hyprlang"|hyprland\\.conf|noctalia\\.conf|windowrulev2|renderBlock|extraConfig = lib\\.mkAfter' \
          ${../../modules/features/desktop/hyprland} \
          ${../../modules/features/desktop/hyprland-animations.nix} \
          ${../../modules/features/desktop/noctalia.nix} \
          ${../../modules/lib/hyprland-rules.nix}; then
          echo "legacy Hyprland/Noctalia configuration path or renderer found" >&2
          exit 1
        fi

        grep -Fq 'configType = "lua"' ${../../modules/features/desktop/hyprland/default.nix}
        grep -Fq 'extraLuaFiles."sinnix-startup.lua"' ${../../modules/features/desktop/hyprland/default.nix}
        grep -Fq 'noctalia.lua' ${../../modules/features/desktop/noctalia.nix}
        grep -Fq 'bind = bindings.bindd ++ bindings.binddl ++ bindings.binddm' ${../../modules/features/desktop/hyprland/default.nix}
        grep -Fq 'window_rule = rules.windowRules' ${../../modules/features/desktop/hyprland/default.nix}
        grep -Fq 'layer_rule = rules.layerRules' ${../../modules/features/desktop/hyprland/default.nix}

        # Every bind family is converted to a call with a description, while
        # locked and mouse options remain explicit semantic Lua options.
        grep -Fq 'mkLuaInline' ${../../modules/features/desktop/hyprland/bindings.nix}
        grep -Fq 'description' ${../../modules/features/desktop/hyprland/bindings.nix}
        grep -Fq 'locked = true' ${../../modules/features/desktop/hyprland/bindings.nix}
        grep -Fq 'mouse = true' ${../../modules/features/desktop/hyprland/bindings.nix}
        grep -Fq 'windowRules' ${../../modules/features/desktop/hyprland/rules.nix}
        grep -Fq 'layerRules' ${../../modules/features/desktop/hyprland/rules.nix}
        grep -Fq 'curve = [' ${../../modules/features/desktop/hyprland-animations.nix}
        grep -Fq 'animation = [' ${../../modules/features/desktop/hyprland-animations.nix}

        # Native Noctalia integration is the generated Lua module; no second
        # polling/color bridge may recreate the old conf authority.
        if grep -REn 'noctalia-hyprland-colors|PathChanged.*hypr|hyprland-colors' ${../../modules/features/desktop/noctalia.nix}; then
          echo "obsolete Noctalia color bridge found" >&2
          exit 1
        fi
        touch "$out"
      '';
    };
}
