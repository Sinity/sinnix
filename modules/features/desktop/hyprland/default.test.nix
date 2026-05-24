{
  lib,
  mkFeatureTest,
  hmFor,
  ...
}:
mkFeatureTest {
  name = "desktop-hyprland";
  feature = "sinnix.features.desktop.hyprland.enable";
  assertions =
    config:
    let
      hm = hmFor config;
      binds = hm.wayland.windowManager.hyprland.settings.bind or [ ];
      debug = hm.wayland.windowManager.hyprland.settings.debug or { };
      sudoRules = config.security.sudo.extraRules or [ ];
      packageNames = map (pkg: lib.getName pkg) config.environment.systemPackages;
    in
    [
      {
        assertion = config.sinnix.features.desktop.hyprland.enable;
        message = "Hyprland must remain default-on with the rest of the desktop feature catalog";
      }
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
        assertion = builtins.elem "uwsm" packageNames;
        message = "TTY login autostart must have uwsm on the system PATH";
      }
      {
        assertion =
          config.systemd.user.units."wayland-session-bindpid@.service".overrideStrategy == "asDropin"
          &&
            lib.hasInfix "X-RestartIfChanged=false"
              config.systemd.user.units."wayland-session-bindpid@.service".text;
        message = "nixos-rebuild switch must not restart UWSM's bindpid unit and tear down Hyprland";
      }
      {
        assertion =
          debug.disable_logs == true && debug.disable_time == true && debug.enable_stdout_logs == false;
        message = "Hyprland debug logs must stay disabled outside targeted crash forensics";
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
