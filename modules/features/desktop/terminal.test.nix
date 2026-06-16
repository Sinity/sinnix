{
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
        assertion = hm.programs.kitty.settings.auto_reload_config == -1;
        message = "Kitty automatic config reload must stay disabled to avoid runaway inotify watches";
      }
      {
        assertion = hm.programs.kitty.settings.allow_remote_control == "socket-only";
        message = "Kitty remote control must stay socket-only";
      }
    ];
}
