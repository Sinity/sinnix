{ lib, mkFeatureTest, hmFor, ... }:
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
        assertion =
          hm.programs.kitty.settings.shell == "${hm.home.homeDirectory}/.local/bin/sinnix-captured-shell";
        message = "Kitty must launch through the capture wrapper";
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
