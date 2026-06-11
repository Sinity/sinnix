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
        assertion = hm.programs.kitty.enable;
        message = "Kitty must be enabled";
      }
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
        assertion =
          hm.programs.kitty.settings.background == "#101014"
          && hm.programs.kitty.settings.foreground == "#e6e1e5"
          && hm.programs.kitty.settings.color5 == "#d0bcff";
        message = "Kitty must carry an explicit Noctalia-aligned palette instead of relying on Stylix includes";
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
