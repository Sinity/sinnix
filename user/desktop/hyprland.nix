# Hyprland window manager configuration
#
# STYLIX MANAGES (from modules/ui.nix):
#   - Wallpaper (via hyprpaper service - DO NOT add hyprpaper config here)
#   - Colors (inherited from base16Scheme)
#   - Fonts
#
# THIS FILE MANAGES:
#   - Core Hyprland settings (input, general, decoration, animations)
#   - Monitor configuration
#   - Script symlinks to ~/.local/bin
#
# SUBMODULES:
#   - hyprland-bindings.nix: All keybindings (bind, bindl, bindm)
#   - hyprland-rules.nix: Window rules (windowrule, windowrulev2)
#   - hyprland-lock.nix: Screen locking and idle management (hypridle, hyprlock)
{
  pkgs,
  inputs,
  lib,
  sinnix,
  ...
}:
let
  flakePath = inputs.self;
  asset = rel: "${flakePath}/assets/${rel}";
  script = rel: "${flakePath}/scripts/${rel}";

  bindings = import ./hyprland-bindings.nix { inherit inputs pkgs sinnix; };
  rules = import ./hyprland-rules.nix;
in
{
  imports = [
    ./hyprland-lock.nix
  ];

  wayland.windowManager.hyprland = {
    enable = true;
    xwayland.enable = true;
    systemd.enable = false;

    settings = {
      exec-once = [
        "uwsm finalize"
      ];

      monitor = [
        ",3840x2160@120,auto,1,bitdepth,10,cm,hdr,sdrbrightness,1.4,sdrsaturation,1.0"
      ];

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
        disable_logs = false;
        disable_time = false;
        enable_stdout_logs = true;
      };

      decoration = {
        rounding = 0;
        active_opacity = 1.0;
        inactive_opacity = 0.7;
        dim_inactive = true;
        dim_strength = 0.3;

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
      inherit (rules) windowrule;
    };
  };

  home.file = {
    ".local/bin/kb-capture" = {
      source = script "kb-capture";
      executable = true;
    };
    ".local/bin/idea-session" = {
      source = script "idea-session";
      executable = true;
    };
    ".config/idea-session/base-agents.md" = {
      source = asset "session/base-agents.md";
    };
    ".local/bin/rawlog" = {
      source = script "rawlog";
      executable = true;
    };
    ".local/bin/toggle-scratch" = {
      source = script "toggle-scratch";
      executable = true;
    };
    ".local/bin/combine-files" = {
      source = script "combine-files";
      executable = true;
    };
    ".local/bin/rawlog-capture" = {
      source = script "rawlog-capture";
      executable = true;
    };
    ".local/bin/kitty-grid" = {
      source = script "kitty-grid";
      executable = true;
    };
    ".local/bin/rawlog-capture-session" = {
      source = script "rawlog-capture-session";
      executable = true;
    };
    ".local/bin/log-to-knowledgebase" = {
      source = script "rawlog";
      executable = true;
    };
    ".config/scratchpads/term.conf" = {
      text = ''
        # shellcheck shell=bash
        COMMAND=(${pkgs.kitty}/bin/kitty --class scratchpad-terminal)
        CLASS="scratchpad-terminal"
        WORKSPACE="scratch_term"
      '';
    };
    ".config/scratchpads/notes.conf" = {
      text = ''
        # shellcheck shell=bash
        COMMAND=(${pkgs.kitty}/bin/kitty --class notes-scratch -d /realm/knowledgebase ${pkgs.neovim}/bin/nvim)
        CLASS="notes-scratch"
        WORKSPACE="scratch_notes"
      '';
    };
    ".config/scratchpads/rawlog.conf" = {
      text = ''
        # shellcheck shell=bash
        COMMAND=(${pkgs.kitty}/bin/kitty --class rawlog-capture --instance-group rawlog --single-instance --override font_size=22 sh -lc "$HOME/.local/bin/rawlog-capture-session")
        CLASS="rawlog-capture"
        WORKSPACE="scratch_rawlog"
        WAIT_FOR_WINDOW_TRIES=50
      '';
    };
    ".config/scratchpads/spotify.conf" = {
      text = ''
        # shellcheck shell=bash
        COMMAND=(spotify)
        CLASS="Spotify"
        CLASS_PATTERN="(?i)^spotify$"
        WORKSPACE="scratch_spotify"
        WAIT_FOR_WINDOW_TRIES=100
      '';
    };
  };

  home.packages = with pkgs; [
    brightnessctl
    grim
    slurp
    grimblast
    wl-screenrec
  ];

  systemd.user.services.hyprpaper.Unit.X-Restart-Triggers = lib.mkForce [ ];
}
