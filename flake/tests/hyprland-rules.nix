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
      hm = hmFor evaluated.config;
      settings = hm.wayland.windowManager.hyprland.settings;
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

      checks.hyprland-login-launch = pkgs.runCommand "sinnix-hyprland-login-launch"
        {
          nativeBuildInputs = [ pkgs.zsh ];
        }
        ''
          mkdir bin home runtime
          cat > bin/tty <<'EOF_TTY'
          #!/bin/sh
          printf '/dev/tty1\n'
          EOF_TTY
          cat > bin/id <<'EOF_ID'
          #!/bin/sh
          test "$1" = -un
          printf 'sinity\n'
          EOF_ID
          cat > bin/uwsm <<'EOF_UWSM'
          #!/bin/sh
          printf '%s\n' "$@" > "$HOME/uwsm-args"
          EOF_UWSM
          chmod +x bin/id bin/tty bin/uwsm
          cat > login.zsh <<'EOF_LOGIN'
          ${hm.programs.zsh.loginExtra}
          EOF_LOGIN
          HOME="$PWD/home" PATH="$PWD/bin:$PATH" zsh login.zsh
          diff -u - "$PWD/home/uwsm-args" <<EOF_ARGS
          start
          -e
          -D
          Hyprland
          --
          ${hyprland}/bin/Hyprland
          --config
          $PWD/home/.config/hypr/hyprland.lua
          EOF_ARGS
          uwsm_parse=$(
            HOME="$PWD/home" XDG_RUNTIME_DIR="$PWD/runtime" \
              ${pkgs.uwsm}/bin/uwsm start -n -e -D Hyprland -- \
                ${hyprland}/bin/Hyprland --config "$PWD/home/.config/hypr/hyprland.lua" \
                2>&1 || true
          )
          printf '%s\n' "$uwsm_parse" | grep -F \
            "Command Line: ${hyprland}/bin/Hyprland --config $PWD/home/.config/hypr/hyprland.lua"
          touch "$out"
        '';

      checks.hyprland-navigation = pkgs.runCommand "sinnix-hyprland-navigation"
        {
          nativeBuildInputs = [ pkgs.bash ];
        }
        ''
          mkdir bin
          cat > bin/hyprctl <<'EOF_HYPRCTL'
          #!${pkgs.runtimeShell}
          printf '%s\n' "$*" >> "$HYPR_RECORD"
          EOF_HYPRCTL
          cat > bin/jq <<'EOF_JQ'
          #!${pkgs.runtimeShell}
          exit 1
          EOF_JQ
          chmod +x bin/hyprctl bin/jq
          export HYPR_RECORD="$PWD/hyprctl-calls"
          export PATH="$PWD/bin:$PATH"

          nav=${../../scripts/kitty-hypr-nav}
          ${pkgs.bash}/bin/bash "$nav" focus left
          ${pkgs.bash}/bin/bash "$nav" focus right
          ${pkgs.bash}/bin/bash "$nav" focus up
          ${pkgs.bash}/bin/bash "$nav" focus down
          ${pkgs.bash}/bin/bash "$nav" move up
          ${pkgs.bash}/bin/bash "$nav" resize down

          diff -u - "$HYPR_RECORD" <<'EOF_EXPECTED'
          eval hl.dispatch(hl.dsp.focus({ direction = "left" }))
          eval hl.dispatch(hl.dsp.focus({ direction = "right" }))
          eval hl.dispatch(hl.dsp.focus({ direction = "up" }))
          eval hl.dispatch(hl.dsp.focus({ direction = "down" }))
          eval hl.dispatch(hl.dsp.window.move({ direction = "up" }))
          eval hl.dispatch(hl.dsp.window.resize({ x = 0, y = 80, relative = true }))
          EOF_EXPECTED
          touch "$out"
        '';
    };
}
