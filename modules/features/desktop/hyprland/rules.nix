# Hyprland window rules configuration
#
# Uses the windowrule {} block syntax (Hyprland 0.53+)
# All rules defined via DSL helpers from lib/hyprland-rules.nix
#
# scratchpadSpecs: list of { name, class, workspace, size } from scratchpads.nix
{
  lib,
  scratchpadSpecs ? [ ],
}:
let
  # Import rules DSL
  rulesDsl = import ../../../lib/hyprland-rules.nix { inherit lib; };
  inherit (rulesDsl)
    mkRule
    mkScratchpad
    mkBrowserScratchpad
    mkDialog
    mkIdleInhibit
    renderBlock
    ;

  # ========================================
  # Idle Inhibit Rules
  # ========================================
  idleRules = [
    {
      mode = "focus";
      class = "^(mpv)$";
    }
    {
      mode = "fullscreen";
      class = "^(firefox)$";
    }
    {
      mode = "fullscreen";
      class = "^(qutebrowser)$";
    }
    {
      mode = "focus";
      title = ".*[Yy]ou[Tt]ube.*";
    }
    {
      mode = "focus";
      title = ".*- YouTube$";
    }
    {
      mode = "focus";
      title = ".*YouTube.*";
    }
    {
      mode = "focus";
      title = ".*Netflix.*";
    }
    {
      mode = "focus";
      title = ".*Twitch.*";
    }
    {
      mode = "focus";
      title = ".*Prime Video.*";
    }
  ];

  idleBlocks = lib.imap0 mkIdleInhibit idleRules;

  # ========================================
  # Dialog Rules
  # ========================================
  dialogRules = [
    (mkDialog "open-file" { title = "^(Open File)$"; })
    (mkDialog "save-as" { title = "^(Save As)$"; })
    (mkDialog "nm-connection-editor" { class = "^(nm-connection-editor)$"; })
  ];

  # ========================================
  # Picture-in-Picture
  # ========================================
  pipRule = mkRule "picture-in-picture" {
    title = "^(Picture-in-Picture)$";
    float = true;
    pin = true;
    size = {
      w = 480;
      h = 270;
    };
    move = {
      x = "(monitor_w-500)";
      y = "50";
    };
  };

  # ========================================
  # Scratchpad Rules (from scratchpads.nix)
  # ========================================
  scratchpadRules = map (
    spec:
    mkScratchpad spec.name {
      inherit (spec) class workspace size;
    }
  ) scratchpadSpecs;

  # Browser scratchpads (using specialized helper)
  browserScratchpads = map mkBrowserScratchpad [
    "chatgpt"
    "claude"
    "aistudio"
    "raindrop"
    "ytmusic"
    "youtube"
  ];

  # ========================================
  # Music Workspace Rules
  # ========================================
  musicRules = [
    (mkRule "music-classic-player" {
      class = "^(music)$";
      workspace = "special:music";
    })
    (mkRule "music-ncspot" {
      title = "^(ncspot)$";
      workspace = "special:music";
    })
    (mkRule "music-volume-control" {
      class = "^(pwvucontrol)$";
      workspace = "special:music";
      float = true;
      opacity = 0.8;
    })
    (mkRule "music-blueman" {
      class = "^(blueman-manager)$";
      workspace = "special:music";
      float = true;
      size = {
        w = 0.40;
        h = 0.45;
      };
      move = {
        x = "(monitor_w*0.02)";
        y = "(monitor_h*0.55)";
      };
      opacity = 0.8;
    })
  ];

  # ========================================
  # Application-Specific Rules
  # ========================================
  appRules = [
    (mkRule "clipse-manager" {
      class = "^(clipse)$";
      float = true;
      center = true;
      size = {
        w = 2000;
        h = 1000;
      };
    })
    (mkRule "steam-games" {
      class = "^(steam_app_.*)$";
      workspace = "5";
      fullscreen = true;
      immediate = true;
      idleinhibit = "always";
    })
    (mkRule "gamescope" {
      class = "^(gamescope)$";
      workspace = "5";
      fullscreen = true;
      immediate = true;
      idleinhibit = "always";
    })
    (mkRule "xdg-portal" {
      class = "^(xdg-desktop-portal-gtk)$";
      float = true;
      center = true;
      size = {
        w = 1200;
        h = 800;
      };
    })
    (mkRule "qutebrowser-main" {
      class = "^(qutebrowser)$";
      tile = true;
      group = "set";
    })
    (mkRule "qutebrowser-floating" {
      class = "^(qutebrowser)$";
      floating = true;
      float = true;
      size = {
        w = 0.28;
        h = 0.24;
      };
      move = {
        x = "(monitor_w*0.70)";
        y = "(monitor_h*0.06)";
      };
    })
    (mkRule "imv-floating" {
      class = "^(imv)$";
      float = true;
      center = true;
    })
    # Floating, dismissable file-preview popup. scripts/open-text-preview launches
    # `kitty --app-id=sinnix-preview -- bat`; wired as the text/* default handler
    # in modules/features/desktop/mime.nix.
    (mkRule "sinnix-text-preview" {
      class = "^(sinnix-preview)$";
      float = true;
      center = true;
      size = {
        w = 0.6;
        h = 0.7;
      };
    })
  ];

  # ========================================
  # Combine All Rules
  # ========================================
  allBlockRules =
    dialogRules
    ++ [ pipRule ]
    ++ musicRules
    ++ scratchpadRules
    ++ browserScratchpads
    ++ appRules
    ++ idleBlocks;

in
{
  windowrule = [ ];
  windowrulev2 = [ ];
  extraConfig = lib.concatMapStringsSep "\n\n" renderBlock allBlockRules + "\n";
}
