{
  lib,
  config,
  pkgs,
  ...
}:
let
  cfg = config.sinnix.features.desktop.hyprland;
  user = config.sinnix.user.name;
  hyprlandPkg = config.programs.hyprland.package or pkgs.hyprland;

  # Helpers for home-manager config
  repoRoot = config.sinnix.paths.projectRoot;
  knowledgebaseRoot = config.sinnix.projects.knowledgebase;
  scriptPath = rel: "${repoRoot}/scripts/${rel}";

  # Helper to import sub-modules which might need args
  bindings = import ./bindings.nix {
    inherit pkgs;
    sinnix = config.sinnix;
  };
  rules = import ./rules.nix { inherit lib hyprlandPkg; };

  # Lock configuration needs to be adapted since it was a HM module
  # We will inline or import it within the HM block

  mkLinkCmd = link: ''
    ln -sf ${scriptPath link.source} "$HOME/.local/bin/${link.target}"
    chmod +x "$HOME/.local/bin/${link.target}"
  '';

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
      # Force UWSM for proper systemd-managed session (required for XDG portal reliability)
      withUWSM = lib.mkForce true;
      package = lib.mkDefault pkgs.hyprland;
      portalPackage = lib.mkDefault pkgs.xdg-desktop-portal-hyprland;
    };

    # Expose wayland-sessions directory for UWSM to discover desktop files
    environment.pathsToLink = [ "/share/wayland-sessions" ];

    # -------------------------------------------------------------------------
    # User Level Configuration (Home Manager)
    # -------------------------------------------------------------------------
    home-manager.users.${user} =
      { pkgs, lib, ... }:
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
            exec-once = [ "uwsm finalize" ];

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
              # Override stylix which sets this true; keep logo visible during startup
              disable_hyprland_logo = lib.mkForce false;
              vrr = 2;
              mouse_move_enables_dpms = true;
              key_press_enables_dpms = true;
              always_follow_on_dnd = true;
              focus_on_activate = true;
              middle_click_paste = true;
              enable_swallow = true;
              swallow_regex = "^(kitty)$";
            };

            debug = {
              disable_logs = true;
              disable_time = false;
              enable_stdout_logs = false;
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

        home.file = {
          ".config/scratchpads/term.conf".text = ''
            COMMAND=(${pkgs.kitty}/bin/kitty --class scratchpad-terminal)
            CLASS="scratchpad-terminal"
            WORKSPACE="scratch_term"
            WIDTH_RATIO=0.75
            HEIGHT_RATIO=0.55
          '';
          ".config/scratchpads/notes.conf".text = ''
            COMMAND=(${pkgs.kitty}/bin/kitty --class notes-scratch -d ${knowledgebaseRoot} ${pkgs.neovim}/bin/nvim)
            CLASS="notes-scratch"
            WORKSPACE="scratch_notes"
            WIDTH_RATIO=0.70
            HEIGHT_RATIO=0.50
          '';
          ".config/scratchpads/rawlog.conf".text = ''
            COMMAND=(${pkgs.kitty}/bin/kitty --class rawlog-capture --instance-group rawlog --single-instance --override font_size=22 sh -lc "$HOME/.local/bin/rawlog-loop")
            CLASS="rawlog-capture"
            WORKSPACE="scratch_rawlog"
            WAIT_FOR_WINDOW_TRIES=50
            WIDTH_RATIO=0.72
            HEIGHT_RATIO=0.48
          '';
          ".config/scratchpads/spotify.conf".text = ''
            COMMAND=(spotify)
            CLASS="Spotify"
            CLASS_PATTERN="(?i)^spotify$"
            WORKSPACE="scratch_spotify"
            WAIT_FOR_WINDOW_TRIES=100
          '';
        };

        home.activation.hyprlandScriptLinks = lib.hm.dag.entryAfter [ "writeBoundary" ] ''
          mkdir -p "$HOME/.local/bin"
          ${lib.concatMapStrings mkLinkCmd scriptLinks}
        '';

        home.packages = with pkgs; [
          brightnessctl
          grim
          slurp
          grimblast
          wl-screenrec
          xdg-desktop-portal-gtk
        ];

        # Prevent hyprpaper restarts on config changes (wallpaper is set once at login)
        systemd.user.services.hyprpaper.Unit.X-Restart-Triggers = lib.mkForce [ ];
      };
  };
}
