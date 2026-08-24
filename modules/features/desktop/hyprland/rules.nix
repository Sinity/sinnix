# Hyprland window and layer rules for the Lua configuration provider.
#
# Each entry is a semantic table consumed by hl.window_rule / hl.layer_rule;
# The module emits tables only; the old string renderer is gone.
{
  lib,
  scratchpadSpecs ? [ ],
}:
let
  rulesDsl = import ../../../lib/hyprland-rules.nix { inherit lib; };
  inherit (rulesDsl)
    mkRule
    mkScratchpad
    mkDialog
    mkIdleInhibit
    mkLayerRule
    ;

  idleRules = [
    {
      mode = "focus";
      class = "^(mpv)$";
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
  ];
  idle = lib.imap0 mkIdleInhibit idleRules;
  dialogs = [
    (mkDialog "open-file" { title = "^(Open File)$"; })
    (mkDialog "save-as" { title = "^(Save As)$"; })
    (mkDialog "nm-connection-editor" { class = "^(nm-connection-editor)$"; })
  ];
  pip = mkRule "picture-in-picture" {
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
  scratchpads = map (
    spec:
    mkScratchpad spec.name {
      inherit (spec) class workspace size;
    }
  ) scratchpadSpecs;
  applications = [
    (mkRule "agent-browser-window" {
      initialTitle = "^sinnix-agent-window-.*$";
      workspace = "special:agentbrowser silent";
      tile = true;
      noInitialFocus = true;
      focusOnActivate = false;
      suppressEvent = "activate activatefocus";
    })
    (mkRule "kitty-focus-opacity" {
      class = "^(kitty)$";
      noBlur = true;
      opacity = {
        active = 1.0;
        inactive = 0.70;
      };
    })
    (mkRule "chrome-focus-opacity" {
      class = "^(google-chrome|google-chrome-unstable|chromium-browser|Chromium)$";
      opacity = {
        active = 1.0;
        inactive = 0.82;
      };
    })
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
      idleInhibit = "always";
    })
    (mkRule "gamescope" {
      class = "^(gamescope)$";
      workspace = "5";
      fullscreen = true;
      immediate = true;
      idleInhibit = "always";
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
    (mkRule "imv-floating" {
      class = "^(imv)$";
      float = true;
      center = true;
    })
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
in
{
  windowRules = dialogs ++ [ pip ] ++ scratchpads ++ applications ++ idle;
  layerRules = [ ];
}
