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
    enable = lib.mkEnableOption "Hyprland Window Manager (Atomic Module)";
  };

  config = lib.mkIf cfg.enable {
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

    # Prevent nixos-rebuild switch from tearing down the running graphical
    # session.  uwsm's wayland-session-bindpid@<HYPRLAND_PID>.service waits
    # on Hyprland's PID with `waitpid` and fires
    # `OnSuccess=wayland-session-shutdown.target` on clean exit — which
    # triggers a graceful session teardown.  When switch-to-configuration
    # restarts this unit because its store path changed (it embeds the
    # util-linux store path in ExecStart), SIGTERM exits waitpid cleanly
    # → OnSuccess fires → graphical-session.target stops → every kitty
    # scope under app.slice is reaped.  Annotating the template with
    # X-RestartIfChanged=false tells switch-to-configuration to leave the
    # running instance alone across rebuilds; new sessions still pick up
    # the updated unit on next login.
    systemd.user.units."wayland-session-bindpid@.service" = {
      overrideStrategy = "asDropin";
      text = ''
        [Unit]
        X-RestartIfChanged=false
      '';
    };

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
        imports = [ ./lock.nix ];

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
          package = hyprlandPkg;
          xwayland.enable = true;
          systemd.enable = false;

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
            };

            dwindle = {
              force_split = 0;
              special_scale_factor = 1.0;
              split_width_multiplier = 1.0;
              use_active_for_splits = true;
              pseudotile = "yes";
              preserve_split = "yes";
            };

            misc = {
              enable_anr_dialog = false;
              # why mkForce: stylix sets this true; keep the logo visible
              # during startup as a "compositor alive" indicator.
              disable_hyprland_logo = lib.mkForce false;
              vrr = 2;
              mouse_move_enables_dpms = true;
              key_press_enables_dpms = true;
              always_follow_on_dnd = true;
              focus_on_activate = true;
              middle_click_paste = true;
              enable_swallow = false;
            };

            debug = {
              disable_logs = false;
              disable_time = false;
              # Route Hyprland logs through systemd journal (already persisted
              # to /realm/data/captures/syslog/journal/). Critical for post-
              # mortem crash analysis — the file-based log in /run/user is tmpfs.
              enable_stdout_logs = true;
            };

            decoration = {
              rounding = 0;
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
            windowrulev2 = if rules ? windowrulev2 then rules.windowrulev2 else [ ];
          };

          extraConfig =
            let
              extra = if rules ? extraConfig then rules.extraConfig else "";
            in
            lib.mkAfter extra;
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
          xdg-desktop-portal-gtk
        ];

        # why mkForce: home-manager auto-injects X-Restart-Triggers from
        # config-file hashes. The wallpaper is set once at login; flushing
        # restarts on every HM rebuild causes a visible flash.
        systemd.user.services.hyprpaper.Unit.X-Restart-Triggers = lib.mkForce [ ];
      };
  };
}
