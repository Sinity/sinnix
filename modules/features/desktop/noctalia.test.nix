{
  lib,
  mkFeatureTest,
  hmFor,
  ...
}:
mkFeatureTest {
  name = "desktop-noctalia";
  feature = "sinnix.features.desktop.noctalia.enable";
  assertions =
    config:
    let
      hm = hmFor config;
      noctaliaConfig = hm.xdg.configFile."noctalia/config.toml" or { };
    in
    [
      {
        assertion =
          noctaliaConfig.force == true
          && noctaliaConfig ? source
          && lib.hasSuffix "-hm_config.toml" (builtins.toString noctaliaConfig.source);
        message = "Noctalia config.toml must stay writable through the repo dotfile symlink";
      }
      {
        assertion =
          !(hm.systemd.user.services ? noctalia-hyprland-reload)
          && !(hm.systemd.user.paths ? noctalia-hyprland-reload);
        message = "Noctalia wallpaper/template updates must not trigger full Hyprland reloads";
      }
      {
        assertion =
          (hm.systemd.user.services ? noctalia-hyprland-colors)
          && (hm.systemd.user.paths ? noctalia-hyprland-colors)
          && !(lib.hasInfix "hyprctl reload" (
            builtins.toString hm.systemd.user.services.noctalia-hyprland-colors.Service.ExecStart
          ));
        message = "Noctalia must update Hyprland colors through Lua eval updates, not full reloads";
      }
    ];
}
