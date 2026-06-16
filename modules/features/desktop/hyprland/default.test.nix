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
      protectedUWSMUnits = [
        "wayland-session-bindpid@.service"
        "wayland-wm@.service"
        "wayland-wm-env@.service"
        "wayland-session@.target"
        "wayland-session-envelope@.target"
        "xdg-desktop-portal-hyprland.service"
      ];
      packageNames = map (pkg: lib.getName pkg) config.environment.systemPackages;
    in
    [
      {
        assertion = config.programs.hyprland.withUWSM;
        message = "UWSM must be enabled";
      }
      {
        assertion = hm.programs.zsh.loginExtra != "";
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
        ) protectedUWSMUnits;
        message = "nixos-rebuild switch must not restart or reload UWSM units and tear down Hyprland";
      }
      {
        assertion = hyprConfig.force == true && (hyprConfig.onChange or null) == "";
        message = "Hyprland config must overwrite stale generated files without activation-time reloads";
      }
      {
        assertion = hm.home.activation ? seedNoctaliaHyprlandTheme;
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
    ];
}
