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
    mkLayerRule
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
    (mkRule "kitty-focus-opacity" {
      class = "^(kitty)$";
      noBlur = true;
      # Native per-app focus/unfocus fade, replacing the old
      # kitty-focus-opacity script+service (hyprctl socket2 listener calling
      # `kitty @ set-background-opacity` per focus event -- laggy). Hyprland
      # applies this on focus change with zero IPC round-trip. Kitty's own
      # background_opacity (terminal.nix) stays static; this windowrule does
      # the focus differentiation, overriding the global
      # decoration.active_opacity/inactive_opacity = 1.0 (kept opaque for
      # every other app) for the kitty class only.
      opacity = {
        active = 1.0;
        inactive = 0.70;
      };
    })
    # The browser gets the same focus differentiation as the terminal.
    #
    # Not cosmetic symmetry: the whole point of dimming unfocused windows is
    # that "which window am I typing into" is answerable at a glance, and a
    # browser that stays fully opaque while everything around it fades is the
    # one window the cue does not cover. It was left out because kitty's rule
    # started life as a replacement for a kitty-specific IPC script, not
    # because the browser was judged to want opaque.
    #
    # Slightly less dimming than kitty's 0.70: page content is arbitrary
    # imagery rather than text on a flat background, and the same alpha reads
    # as considerably murkier over a photo than over a terminal.
    (mkRule "chrome-focus-opacity" {
      class = "^(google-chrome|google-chrome-unstable|chromium-browser|Chromium)$";
      opacity = {
        active = 1.0;
        inactive = 0.82;
      };
    })
    # Ambient reading-stack widget (sinnix-reading-stack-widget): pinned
    # (visible on every workspace) in a small corner window -- this IS the
    # "standing visibility" mechanism the reading-stack design depends on
    # (see the script's own docstring). Small/opaque/no-blur so it reads as
    # a persistent status element, not a normal floating window.
    (mkRule "reading-stack-widget" {
      class = "^(reading-stack-widget)$";
      float = true;
      pin = true;
      noBlur = true;
      size = {
        w = 420;
        h = 260;
      };
      move = {
        x = "(monitor_w-440)";
        y = "(monitor_h-280)";
      };
      opacity = 0.9;
    })
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
  # Layer Rules
  # ========================================
  # Noctalia anchors its notification layer full-height (so toasts can stack
  # downward) and Quickshell requests compositor blur for the whole layer
  # surface via a client-side background-effect protocol -- not through any
  # hyprlang layerrule, which is why no rule needs to (or can) turn blur ON
  # for it. The problem is that Hyprland then blurs the layer's full rect,
  # and the ~90% of it below the toast card is near-fully-transparent, so
  # blurring pulls those pixels toward a local mean: a dimmed column behind
  # and below every toast. `ignore_alpha` discards near-transparent pixels
  # from the blur sample regardless of which mechanism turned blur on for
  # the surface, which is why it still fixes this even though `blur` here is
  # belt-and-braces (Hyprland's own docs example is the identical rofi case).
  # See sinnix-nzr9: the earlier "hyprlang layerrule has no matcher" finding
  # was true only for the deprecated inline `layerrule = <field>, <ns>` form;
  # the "layerrule v2" special-category form used here (registered
  # separately in Hyprland's legacy config manager) still carries a
  # namespace matcher, confirmed with `Hyprland --verify-config`.
  layerRules = [
    (mkLayerRule "noctalia-notification-blur" {
      namespace = "noctalia-notification";
      blur = true;
      ignoreAlpha = 0.5;
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
    ++ idleBlocks
    ++ layerRules;

in
{
  windowrule = [ ];
  windowrulev2 = [ ];
  extraConfig = lib.concatMapStringsSep "\n\n" renderBlock allBlockRules + "\n";
}
