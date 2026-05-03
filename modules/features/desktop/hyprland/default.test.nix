{ lib, mkFeatureTest, hmFor, ... }:
mkFeatureTest {
  name = "desktop-hyprland";
  feature = "sinnix.features.desktop.hyprland.enable";
  extraModules = [
    (
      { lib, ... }:
      {
        # why mkForce: hermetic-test override; no real GPU in eval VMs.
        hardware.graphics.enable = lib.mkForce false;
      }
    )
  ];
  assertions =
    config:
    let
      hm = hmFor config;
      binds = hm.wayland.windowManager.hyprland.settings.bind or [ ];
      sudoRules = config.security.sudo.extraRules or [ ];
    in
    [
      {
        assertion = config.programs.hyprland.enable;
        message = "Hyprland must be enabled";
      }
      {
        assertion = config.programs.hyprland.withUWSM;
        message = "UWSM must be enabled";
      }
      {
        assertion = lib.hasInfix "exec uwsm start hyprland-uwsm.desktop" (hm.programs.zsh.loginExtra or "");
        message = "TTY Hyprland login must stay unwrapped by default";
      }
      {
        assertion = builtins.any (
          bind: lib.hasInfix "F9, exec, sudo -n" bind && lib.hasInfix "/bin/nuke-builds" bind
        ) binds;
        message = "F9 emergency binding must bypass uwsm and run the packaged root shed script";
      }
      {
        assertion = builtins.any (
          rule:
          builtins.elem config.sinnix.user.name (rule.users or [ ])
          && builtins.any (
            command:
            lib.hasInfix "/bin/nuke-builds" command.command && builtins.elem "NOPASSWD" (command.options or [ ])
          ) (rule.commands or [ ])
        ) sudoRules;
        message = "Hyprland emergency binding must have passwordless sudo for the immutable nuke-builds package";
      }
    ];
}
