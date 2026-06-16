{
  lib,
  mkFeatureTest,
  hmFor,
  ...
}:
mkFeatureTest {
  name = "desktop-terminal";
  feature = "sinnix.features.desktop.terminal.enable";
  assertions =
    config:
    let
      hm = hmFor config;
    in
    [
      {
        assertion = hm.stylix.targets.kitty.enable == false;
        message = "Kitty must not include Stylix Nix-store color files because its config watcher can exhaust inotify watches";
      }
      {
        assertion =
          hm.programs.kitty.settings.shell == "${hm.home.homeDirectory}/.local/bin/sinnix-captured-shell";
        message = "Kitty must launch through the capture wrapper";
      }
      {
        assertion = hm.programs.kitty.settings.font_family == "SauceCodePro Nerd Font Mono";
        message = "Kitty must keep the configured monospace font when Stylix's Kitty target is disabled";
      }
      {
        assertion = hm.programs.kitty.settings.font_size == 16;
        message = "Kitty must keep the configured terminal font size when Stylix's Kitty target is disabled";
      }
      {
        assertion = hm.programs.kitty.settings.auto_reload_config == -1;
        message = "Kitty automatic config reload must stay disabled to avoid runaway inotify watches";
      }
      {
        assertion = hm.programs.kitty.settings.scrollback_lines == 10000;
        message = "Kitty scrollback must stay bounded so high-output agent TUIs do not retain gigabytes";
      }
      {
        assertion = lib.hasInfix "include ~/.config/kitty/themes/noctalia.conf" (
          hm.programs.kitty.extraConfig or ""
        );
        message = "Kitty must consume Noctalia's native generated theme instead of owning colors in Sinnix";
      }
      {
        assertion = hm.programs.kitty.settings.open_url_with == "xdg-open";
        message = "Kitty URL opening must stay delegated to xdg-open";
      }
      {
        assertion = hm.programs.kitty.settings.allow_remote_control == "socket-only";
        message = "Kitty remote control must stay socket-only";
      }
      {
        assertion =
          let
            mode = hm.programs.kitty.shellIntegration.mode or "";
          in
          lib.hasInfix "no-prompt-mark" mode && lib.hasInfix "no-title" mode && lib.hasInfix "no-cursor" mode;
        message = "Kitty shell integration must disable prompt/title/cursor features that interfere with the custom zsh prompt";
      }
    ];
}
