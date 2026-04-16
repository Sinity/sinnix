# Scratchpad Configuration
#
# Single source of truth for scratchpad definitions.
# Generates both:
#   - .conf files for toggle-scratch script
#   - Window rules for Hyprland (via rules.nix DSL)
{
  pkgs,
  lib,
  knowledgebaseRoot,
}:
let
  # Common scratchpad spec:
  # {
  #   class = "class-name";          # Window class to match
  #   workspace = "scratch_name";    # Workspace name (without special: prefix)
  #   size = { w = 0.75; h = 0.55; };# Size as ratios
  #   command = [ "cmd" "args" ];    # Command to launch
  #   classPattern = null;           # Optional regex pattern for class matching
  #   waitTries = null;              # Optional wait tries for slow apps
  # }

  scratchpads = {
    term = {
      class = "scratchpad-terminal";
      workspace = "scratch_term";
      size = {
        w = 0.75;
        h = 0.55;
      };
      command = [
        "${pkgs.kitty}/bin/kitty"
        "--class"
        "scratchpad-terminal"
      ];
    };

    notes = {
      class = "notes-scratch";
      workspace = "scratch_notes";
      size = {
        w = 0.70;
        h = 0.50;
      };
      command = [
        "${pkgs.kitty}/bin/kitty"
        "--class"
        "notes-scratch"
        "-d"
        knowledgebaseRoot
        "${pkgs.neovim}/bin/nvim"
      ];
    };

    rawlog = {
      class = "rawlog-capture";
      workspace = "scratch_rawlog";
      size = {
        w = 0.72;
        h = 0.48;
      };
      command = [
        "${pkgs.kitty}/bin/kitty"
        "--class"
        "rawlog-capture"
        "--instance-group"
        "rawlog"
        "--single-instance"
        "--override"
        "font_size=22"
        "$HOME/.local/bin/rawlog-loop"
      ];
      waitTries = 50;
    };

    spotify = {
      class = "Spotify";
      workspace = "scratch_spotify";
      size = {
        w = 0.85;
        h = 0.85;
      };
      command = [ "spotify" ];
      classPattern = "(?i)^spotify$";
      waitTries = 100;
    };

    weechat = {
      class = "scratchpad-weechat";
      workspace = "scratch_weechat";
      size = {
        w = 0.75;
        h = 0.75;
      };
      command = [
        "${pkgs.kitty}/bin/kitty"
        "--class"
        "scratchpad-weechat"
        "--title"
        "WeeChat"
        "$HOME/.local/bin/weechat-scratchpad"
      ];
    };

    claude = {
      class = "scratchpad-claude";
      workspace = "scratch_claude";
      size = {
        w = 0.85;
        h = 0.85;
      };
      command = [
        "${pkgs.kitty}/bin/kitty"
        "--class"
        "scratchpad-claude"
        "--title"
        "Claude"
        "claude"
      ];
    };

    agent = {
      class = "scratchpad-agent";
      workspace = "scratch_agent";
      size = {
        w = 0.90;
        h = 0.90;
      };
      command = [
        "${pkgs.kitty}/bin/kitty"
        "--class"
        "scratchpad-agent"
        "--title"
        "Agent"
      ];
    };
  };

  # Generate .conf file content for toggle-scratch script
  mkConfContent =
    _name: spec:
    let
      lines = [
        "COMMAND=(${lib.concatStringsSep " " spec.command})"
        ''CLASS="${spec.class}"''
        ''WORKSPACE="${spec.workspace}"''
      ]
      ++ lib.optional (
        spec ? classPattern && spec.classPattern != null
      ) ''CLASS_PATTERN="${spec.classPattern}"''
      ++ lib.optional (
        spec ? waitTries && spec.waitTries != null
      ) "WAIT_FOR_WINDOW_TRIES=${toString spec.waitTries}"
      ++ [
        "WIDTH_RATIO=${toString spec.size.w}"
        "HEIGHT_RATIO=${toString spec.size.h}"
      ];
    in
    lib.concatStringsSep "\n" lines + "\n";

  # Generate home.file entries for all scratchpads
  confFiles = lib.mapAttrs' (name: spec: {
    name = ".config/scratchpads/${name}.conf";
    value = {
      text = mkConfContent name spec;
    };
  }) scratchpads;

  # Export for rules.nix to generate window rules
  # Returns list of { class, workspace, size } for mkScratchpad
  ruleSpecs = lib.mapAttrsToList (name: spec: {
    inherit name;
    class = "^(${spec.class})$";
    workspace = "special:${spec.workspace}";
    inherit (spec) size;
  }) scratchpads;

in
{
  inherit scratchpads confFiles ruleSpecs;
}
