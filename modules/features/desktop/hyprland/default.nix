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
    inherit pkgs scriptPkgs;
    sinnix = config.sinnix;
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
      target = "hdr-screenshot";
      source = "hdr-screenshot";
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
        overrideStrategy = "asDropin";
        text = ''
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
            configType = "hyprlang";
            package = hyprlandPkg;
            xwayland.enable = true;
            systemd.enable = false;

            # NOTE: hyprexpo (workspace overview) intentionally NOT enabled —
            # hyprlandPlugins.hyprexpo fails to compile against this nixpkgs
            # Hyprland pin (missing HookSystemManager.hpp; upstream out of sync).
            # Re-add via the version-matched plugin from the hyprland flake once
            # nixpkgs catches up.

            settings = {
              exec-once = [
                "uwsm finalize"
                # Auto-start weechat scratchpad (hidden in special workspace)
                "uwsm app -- ${pkgs.kitty}/bin/kitty --class scratchpad-weechat --title WeeChat $HOME/.local/bin/weechat-scratchpad"
              ];

              # Override uwsm's "start-hyprland:Hyprland" to clean value
              # Fixes warning from apps like nm-applet that don't understand uwsm format
              env = [ "XDG_CURRENT_DESKTOP,Hyprland" ];

              xwayland.force_zero_scaling = true;

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
                # Noctalia owns the live border palette through its native
                # Hyprland template included below. These are first-session
                # fallbacks before ~/.config/hypr/noctalia.conf exists.
                "col.active_border" = lib.mkForce "rgba(d0bcffee) rgba(a8c7faee) rgba(8fd8d2ee) 45deg";
                "col.inactive_border" = lib.mkForce "rgba(49454faa)";
              };

              dwindle = {
                force_split = 0;
                special_scale_factor = 1.0;
                split_width_multiplier = 1.0;
                use_active_for_splits = true;
                preserve_split = "yes";
              };

              misc = {
                enable_anr_dialog = false;
                # why mkForce: stylix sets this true; keep the logo visible
                # during startup as a "compositor alive" indicator.
                disable_hyprland_logo = lib.mkForce false;
                # Fullscreen VRR causes the AORUS OLED to briefly drop signal
                # when mpv enters or leaves fullscreen.
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

              decoration = {
                rounding = 10;
                active_opacity = 1.0;
                inactive_opacity = 0.96;
                dim_inactive = true;
                dim_strength = 0.03;

                blur = {
                  enabled = true;
                  size = 8;
                  passes = 3;
                  new_optimizations = true;
                  vibrancy = 0.15;
                  vibrancy_darkness = 0.2;
                };

                shadow = {
                  enabled = true;
                  range = 20;
                  render_power = 3;
                  offset = "0 8";
                };
              };

              animations.enabled = false;

              inherit (bindings) bind bindl bindm;
              windowrule = if rules ? windowrule then rules.windowrule else [ ];

              # Smart gaps: a workspace holding a single tiled window (or one
              # fullscreen-tiled window) drops gaps, border, and rounding.
              # Hyprland 0.54 workspace-rule params — supersedes the old
              # windowrulev2 bordersize/rounding hack (deprecated in 0.54).
              workspace = [
                "w[tv1], gapsout:0, gapsin:0, border:false, rounding:false"
                "f[1], gapsout:0, gapsin:0, border:false, rounding:false"
              ];
              # NOTE: bar-layer blur (layerrule) omitted — the inline
              # `layerrule = blur, <ns>` form is rejected by Hyprland 0.54.3
              # (syntax changed). Re-add once the 0.54 layerrule form is
              # confirmed; Noctalia namespaces are noctalia-bar-default /
              # noctalia-wallpaper.
            };

            extraConfig =
              let
                extra = if rules ? extraConfig then rules.extraConfig else "";
              in
              lib.mkAfter ''
                # Generated and live-reloaded by Noctalia's wallpaper-derived
                # Hyprland template. The file is seeded below so first login
                # does not depend on template generation order.
                source = ~/.config/hypr/noctalia.conf

                ${extra}
              '';
          };

          xdg.configFile."hypr/hyprland.conf" = {
            force = true;
            # Home Manager's default onChange runs `hyprctl reload config-only`.
            # During a NixOS switch, unit churn is already risky enough; apply
            # new compositor config on the next session or by explicit reload.
            onChange = lib.mkForce "";
          };

          home.activation.seedNoctaliaHyprlandTheme = lib.hm.dag.entryAfter [ "writeBoundary" ] ''
            theme_file="''${XDG_CONFIG_HOME:-$HOME/.config}/hypr/noctalia.conf"
            if [ ! -e "$theme_file" ]; then
              mkdir -p "$(dirname "$theme_file")"
              printf '%s\n' '# Seed file overwritten by Noctalia native Hyprland template.' > "$theme_file"
            fi
          '';

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

          home.packages = with pkgs; [
            brightnessctl
            grim
            slurp
            grimblast
            imagemagick
            jq
            libnotify
            wl-clipboard
            wl-screenrec
          ];
        };
    })
  ];
}
