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
            {
              assertion =
                let
                  rules = (settings.window_rule or [ ]) ++ (settings.config.window_rule or [ ]);
                in
                lib.any (
                  rule: (rule.name or "") == "agent-terminal-no-focus" && (rule.no_initial_focus or false)
                ) rules;
              message =
                let
                  rules = (settings.window_rule or [ ]) ++ (settings.config.window_rule or [ ]);
                  names = map (rule: toString (rule.name or "?")) rules;
                in
                "Agent-opened Kitty OS windows must not take initial focus or activation. window_rule names: ${lib.concatStringsSep ", " names}";
            }
          ];
      };
      evaluated = evalTestSpec system spec;
      hyprland = evaluated.config.programs.hyprland.package;
      hm = hmFor evaluated.config;
      settings = hm.wayland.windowManager.hyprland.settings;
    in
    {
      checks.hyprland-rules =
        assert lib.hasInfix "hyprctl" hm.xdg.configFile."hypr/hyprland.lua".onChange;
        assert lib.hasInfix "reload" hm.xdg.configFile."hypr/hyprland.lua".onChange;
        pkgs.runCommand "sinnix-hyprland-rules" { } ''
          cat > "$out" <<'EOF_CONTRACT'
          ${builtins.toJSON {
            globalBlur = settings.config.decoration.blur.enabled;
          }}
          EOF_CONTRACT
        '';

      checks.hyprland-lua-config = mkHmRuntimeCheck system {
        name = "hyprland-lua-config";
        inherit evaluated;
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

      checks.hyprland-login-launch =
        pkgs.runCommand "sinnix-hyprland-login-launch"
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
            printf '%s\n' "$HYPRLAND_CONFIG" > "$HOME/hyprland-config-path"
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
            ${hyprland}/bin/start-hyprland
            EOF_ARGS
            test "$(cat "$PWD/home/hyprland-config-path")" = "$PWD/home/.config/hypr/hyprland.lua"
            uwsm_parse=$(
              HOME="$PWD/home" XDG_RUNTIME_DIR="$PWD/runtime" HYPRLAND_CONFIG="$PWD/home/.config/hypr/hyprland.lua" \
                ${pkgs.uwsm}/bin/uwsm start -n -e -D Hyprland -- \
                  ${hyprland}/bin/Hyprland \
                  2>&1 || true
            )
            printf '%s\n' "$uwsm_parse" | grep -F \
              "Command Line: ${hyprland}/bin/Hyprland"
            touch "$out"
          '';

      checks.hyprland-binding-reload =
        pkgs.runCommand "sinnix-hyprland-binding-reload" { nativeBuildInputs = [ pkgs.lua ]; }
          ''
            cat > startup.lua <<'EOF_STARTUP'
            ${hm.wayland.windowManager.hyprland.extraLuaFiles."sinnix-startup.lua".content}
            EOF_STARTUP
            cat > test.lua <<'EOF_TEST'
            local hooks, bindings = {}, {}
            local action = {}
            setmetatable(action, {
              __index = function() return action end,
              __call = function() return action end,
            })
            hl = {
              on = function(event, callback) hooks[event] = callback end,
              unbind = function(key) assert(key == "all"); bindings = {} end,
              bind = function(key, action) assert(bindings[key] == nil); bindings[key] = action end,
              dsp = setmetatable({exec_cmd = function(command) return command end}, {
                __index = function() return action end,
              }),
            }
            dofile("startup.lua")
            for attempt = 1, 2 do
              -- The old main config runs after require(startup), overwriting
              -- these callbacks on every config-only reload.
              bindings.F6 = "uwsm app -- /retired/scripts/toggle-scratch weechat"
              bindings.F8 = "uwsm app -- /retired/scripts/toggle-scratch rawlog"
              bindings.Obsolete = "retired binding"
              hooks["config.reloaded"]()
              assert(bindings.F8 == ${
                lib.generators.toLua { }
                  "uwsm app -- ${evaluated.config.sinnix.paths.projectRoot}/scripts/toggle-scratch rawlog"
              })
              assert(bindings.F6 == ${
                lib.generators.toLua { }
                  "uwsm app -- ${evaluated.config.sinnix.paths.projectRoot}/scripts/toggle-scratch weechat"
              })
              assert(bindings.F7 == "sinnix-chrome-control toggle-agent-workspace")
              assert(bindings.Obsolete == nil)
            end
            EOF_TEST
            lua test.lua
            touch "$out"
          '';

      checks.hyprland-navigation =
        pkgs.runCommand "sinnix-hyprland-navigation"
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
