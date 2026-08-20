{
  lib,
  config,
  pkgs,
  helpers,
  ...
}:
let
  cfg = config.sinnix.features.desktop.hyprland;
  user = config.sinnix.user.name;
  hyprlandPkg = config.programs.hyprland.package or pkgs.hyprland;
  scriptPkgs = helpers.mkSinnixPackagesFor pkgs;

  # Helpers for home-manager config
  repoRoot = config.sinnix.paths.projectRoot;
  knowledgebaseRoot = config.sinnix.projects.knowledgebase;

  # Scratchpad configuration (single source of truth)
  scratchpadData = import ./scratchpads.nix {
    inherit
      pkgs
      lib
      knowledgebaseRoot
      ;
  };

  # Helper to import sub-modules which might need args
  bindings = import ./bindings.nix {
    inherit lib pkgs scriptPkgs;
    inherit (config) sinnix;
  };
  rules = import ./rules.nix {
    inherit lib;
    scratchpadSpecs = scratchpadData.ruleSpecs;
  };

  protectedUWSMUnits = [
    "wayland-session-bindpid@.service"
    "wayland-wm@.service"
    "wayland-wm-env@.service"
    "wayland-session@.target"
    "wayland-session-envelope@.target"
    "xdg-desktop-portal-hyprland.service"
  ];

  scriptLinks = [
    {
      target = "audio";
      source = "audio";
    }
    {
      target = "rawlog";
      source = "rawlog";
    }
    {
      target = "toggle-scratch";
      source = "toggle-scratch";
    }
    {
      target = "rawlog-capture";
      source = "rawlog-capture";
    }
    {
      target = "kitty-grid";
      source = "kitty-grid";
    }
    {
      target = "rawlog-loop";
      source = "rawlog-loop";
    }
    {
      target = "weechat-scratchpad";
      source = "weechat-scratchpad";
    }
    {
      target = "kitty-scrollback-capture";
      source = "kitty-scrollback-capture";
    }
    {
      target = "kitty-scrollback-view";
      source = "kitty-scrollback-view";
    }
    {
      target = "hyprland-ocr";
      source = "hyprland-ocr";
    }
    {
      target = "dismiss-scratchpads";
      source = "dismiss-scratchpads";
    }
  ];
in
{
  options.sinnix.features.desktop.hyprland = {
    enable = (lib.mkEnableOption "Hyprland Window Manager (Atomic Module)") // {
      default = true;
    };
  };

  config = lib.mkMerge [
    # Prevent nixos-rebuild switch from tearing down the running graphical
    # session. UWSM units are tightly bound together; restarting the compositor,
    # envelope, or bindpid units propagates into wayland-session-shutdown.target
    # and kills the active desktop. New unit definitions take effect on next
    # login, while the current session stays intact across rebuilds. Keep this
    # outside cfg.enable so a bad repair generation cannot omit the protection
    # while Hyprland is active.
    {
      systemd.user.units = lib.genAttrs protectedUWSMUnits (_: {
        overrideStrategy = lib.mkForce "asDropin";
        text = lib.mkForce ''
          [Unit]
          X-OnlyManualStart=true
          X-RestartIfChanged=false
          X-ReloadIfChanged=false
        '';
      });
    }

    (lib.mkIf cfg.enable {
      # -------------------------------------------------------------------------
      # System Level Configuration
      # -------------------------------------------------------------------------
      programs.hyprland = {
        enable = lib.mkDefault true;
        # why mkForce: nixos-hyprland defaults withUWSM=false; UWSM is
        # required for proper systemd-managed session (XDG portal reliability).
        withUWSM = lib.mkForce true;
        package = lib.mkDefault pkgs.hyprland;
        portalPackage = lib.mkDefault pkgs.xdg-desktop-portal-hyprland;
      };

      # Expose wayland-sessions directory for UWSM to discover desktop files
      environment.pathsToLink = [ "/share/wayland-sessions" ];

      environment.systemPackages = [
        pkgs.uwsm
      ];

      security.sudo.extraRules = [
        {
          users = [ user ];
          commands = [
            {
              command = "${scriptPkgs.nuke-builds}/bin/nuke-builds";
              options = [ "NOPASSWD" ];
            }
          ];
        }
      ];

      # -------------------------------------------------------------------------
      # User Level Configuration (Home Manager)
      # -------------------------------------------------------------------------
      home-manager.users.${user} =
        {
          pkgs,
          lib,
          config,
          ...
        }:
        {
          imports = [ ./idle.nix ];

          programs.zsh.loginExtra = lib.mkBefore ''
            if [ "$(id -un)" = "${user}" ] && [ -z "$DISPLAY" ]; then
              current_tty=$(tty 2>/dev/null || true)
              if [ "$current_tty" = "/dev/tty1" ] && command -v uwsm >/dev/null 2>&1; then
                exec uwsm start hyprland-uwsm.desktop
              fi
            fi
          '';

          wayland.windowManager.hyprland = {
            enable = true;
            configType = "lua";
            package = hyprlandPkg;
            xwayland.enable = true;
            systemd.enable = false;

            # The Lua provider renders each setting as a semantic hl.* call.
            # Keep one `hl.config` table for compositor options and use the
            # dedicated bind/rule calls for values that are not config keys.
            settings = {
              config = {
                env = [ ];
                xwayland = {
                  force_zero_scaling = true;
                };
                cursor = {
                  no_warps = true;
                };
                input = {
                  kb_layout = "pl";
                  repeat_rate = 40;
                  repeat_delay = 400;
                  mouse_refocus = true;
                  sensitivity = 0;
                  accel_profile = "flat";
                  force_no_accel = 0;
                  scroll_factor = 1;
                  follow_mouse = 1;
                };
                general = {
                  border_size = 3;
                  gaps_in = 10;
                  gaps_out = 20;
                  layout = "dwindle";
                  resize_on_border = true;
                  col = {
                    active_border = {
                      colors = [
                        "rgba(d0bcffee)"
                        "rgba(a8c7faee)"
                        "rgba(8fd8d2ee)"
                      ];
                      angle = 45;
                    };
                    inactive_border = "rgba(49454faa)";
                  };
                };
                dwindle = {
                  force_split = 0;
                  special_scale_factor = 1.0;
                  split_width_multiplier = 1.0;
                  use_active_for_splits = true;
                  preserve_split = true;
                };
                misc = {
                  enable_anr_dialog = false;
                  disable_hyprland_logo = lib.mkForce false;
                  vrr = 0;
                  mouse_move_enables_dpms = true;
                  key_press_enables_dpms = true;
                  always_follow_on_dnd = true;
                  focus_on_activate = true;
                  middle_click_paste = true;
                  enable_swallow = false;
                };
                debug = {
                  disable_logs = true;
                  disable_time = true;
                  enable_stdout_logs = false;
                };
                render = {
                  use_fp16 = false;
                  keep_unmodified_copy = 1;
                  use_shader_blur_blend = true;
                };
                decoration = {
                  rounding = 10;
                  active_opacity = 1.0;
                  inactive_opacity = 1.0;
                  dim_inactive = false;
                  dim_strength = 0.0;
                  blur = {
                    enabled = true;
                  };
                  shadow = {
                    enabled = true;
                    range = 20;
                    render_power = 3;
                    offset = "0 8";
                  };
                };
              };

              env = [
                {
                  _args = [
                    "XDG_CURRENT_DESKTOP"
                    "Hyprland"
                  ];
                }
              ];
              bind = bindings.bindd ++ bindings.binddl ++ bindings.binddm;
              window_rule = rules.windowRules;
              layer_rule = rules.layerRules;
            };

            submaps = bindings.submaps;
            extraConfig = "";
            extraLuaFiles."sinnix-startup.lua" = {
              autoLoad = true;
              content = ''
                hl.on("hyprland.start", function()
                  hl.exec_cmd("uwsm finalize")
                  hl.exec_cmd("uwsm app -- ${pkgs.kitty}/bin/kitty --class scratchpad-weechat --title WeeChat $HOME/.local/bin/weechat-scratchpad")
                  hl.exec_cmd("uwsm app -- ${scriptPkgs.sinnix-nav-capture-daemon}/bin/sinnix-nav-capture-daemon")
                  hl.exec_cmd("uwsm app -- ${pkgs.kitty}/bin/kitty --class reading-stack-widget --title reading-stack ${scriptPkgs.sinnix-reading-stack-widget}/bin/sinnix-reading-stack-widget")
                end)
              '';
            };
          };

          services.hyprpaper.enable = lib.mkForce false;

          xdg.configFile."hypr/shaders" = {
            source = config.lib.file.mkOutOfStoreSymlink "${repoRoot}/dots/hypr/shaders";
            force = true;
          };

          xdg.configFile."hypr/hyprland.lua" = {
            force = true;
            # Home Manager's default onChange runs `hyprctl reload config-only`.
            # During a NixOS switch, unit churn is already risky enough; apply
            # new compositor config on the next session or by explicit reload.
            onChange = lib.mkForce "";
          };

          # Scratchpad config files + script links
          home.file =
            scratchpadData.confFiles
            // lib.listToAttrs (
              map (link: {
                name = ".local/bin/${link.target}";
                value = {
                  source = config.lib.file.mkOutOfStoreSymlink "${repoRoot}/scripts/${link.source}";
                  force = true;
                };
              }) scriptLinks
            );

          # WeeChat must run from login and stay up independent of the F6
          # scratchpad so IRC logs are captured continuously. The old
          # Type=oneshot unit fired once and then stopped tracking the tmux
          # server (Tasks:0); when that server later died (crash/earlyoom)
          # nothing restarted it, so weechat only reappeared when the
          # scratchpad was opened — silently dropping every log line in
          # between. Supervise the tmux server as the unit's main process and
          # restart it if it dies. ExecStartPre clears any session created by
          # the scratchpad attach fallback so the forked server is always the
          # tracked PID. The scratchpad/F6 path now only attaches.
          systemd.user.services.weechat-scratchpad = {
            Unit = {
              Description = "Persistent WeeChat tmux session (attachable via F6 scratchpad)";
              After = [ "default.target" ];
            };
            Service = {
              Type = "forking";
              ExecStartPre = "-${pkgs.tmux}/bin/tmux -S /tmp/tmux-weechat-%U kill-server";
              ExecStart = "${pkgs.tmux}/bin/tmux -S /tmp/tmux-weechat-%U new-session -d -s weechat-persistent ${pkgs.weechat}/bin/weechat";
              ExecStartPost = "${pkgs.tmux}/bin/tmux -S /tmp/tmux-weechat-%U set-option -t weechat-persistent destroy-unattached off";
              ExecStop = "${pkgs.tmux}/bin/tmux -S /tmp/tmux-weechat-%U kill-server";
              Restart = "always";
              RestartSec = 5;
            };
            Install.WantedBy = [ "default.target" ];
          };

          home.packages = with pkgs; [
            brightnessctl
            grim
            slurp
            grimblast
            imagemagick
            jq
            libnotify
            tesseract
            wl-clipboard
            wl-screenrec
          ];
        };
    })
  ];
}
