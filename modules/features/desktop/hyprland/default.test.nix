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
      dwindle = hm.wayland.windowManager.hyprland.settings.dwindle or { };
      debug = hm.wayland.windowManager.hyprland.settings.debug or { };
      render = hm.wayland.windowManager.hyprland.settings.render or { };
      decoration = hm.wayland.windowManager.hyprland.settings.decoration or { };
      hyprConfig = hm.xdg.configFile."hypr/hyprland.conf" or { };
      hyprExtraConfig = hm.wayland.windowManager.hyprland.extraConfig or "";
      protectedUWSMUnits = [
        "wayland-session-bindpid@.service"
        "wayland-wm@.service"
        "wayland-wm-env@.service"
        "wayland-session@.target"
        "wayland-session-envelope@.target"
        "xdg-desktop-portal-hyprland.service"
      ];
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
        assertion = builtins.all (
          name:
          let
            unit = config.systemd.user.units.${name} or { };
          in
          unit.overrideStrategy == "asDropin"
          && lib.hasInfix "[Unit]" unit.text
          && lib.hasInfix "X-OnlyManualStart=true" unit.text
          && lib.hasInfix "X-RestartIfChanged=false" unit.text
          && lib.hasInfix "X-ReloadIfChanged=false" unit.text
          && !(lib.hasInfix "[Service]" unit.text)
        ) protectedUWSMUnits;
        message = "nixos-rebuild switch must not restart or reload UWSM units and tear down Hyprland";
      }
      {
        assertion = hyprConfig.force == true && (hyprConfig.onChange or null) == "";
        message = "Hyprland config must overwrite stale generated files without activation-time reloads";
      }
      {
        assertion =
          lib.hasInfix "source = ~/.config/hypr/noctalia.conf" hyprExtraConfig
          && hm.home.activation ? seedNoctaliaHyprlandTheme;
        message = "Hyprland must consume Noctalia's generated theme without Home Manager owning the generated file";
      }
      {
        assertion = hm.services.hyprpaper.enable == false;
        message = "Noctalia owns wallpaper, so Hyprland must not start hyprpaper";
      }
      {
        assertion =
          decoration.dim_inactive == false
          && decoration.dim_strength == 0.0
          && decoration.active_opacity == 1.0
          && decoration.inactive_opacity == 0.75;
        message = "Hyprland must keep transparent windows without compositor dimming";
      }
      {
        assertion = render.use_fp16 == false;
        message = "Hyprland HDR output must keep FP16 disabled to avoid wallpaper-change dimming";
      }
      {
        assertion = builtins.any (bind: bind == "SUPER, Y, layoutmsg, togglesplit") binds;
        message = "Hyprland split toggle binding must use layoutmsg togglesplit";
      }
      {
        assertion = !(dwindle ? pseudotile);
        message = "Hyprland dwindle config must not emit removed pseudotile option";
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
