# Time-of-day color temperature grading via hyprsunset.
#
# The grading is applied as a color transform matrix through
# `hyprland-ctm-control-v1` (the interface Hyprland's
# `render:non_shader_cm_interop` option describes), not through
# `decoration:screen_shader`. Two consequences:
#
#   - Zero GPU cost by construction: the transform happens in the display
#     pipeline at scanout, not in a per-pixel composite pass.
#   - It does not tint captures. A screen shader sits in the composite path,
#     so screenshots and capture-screen recordings would inherit its color and
#     an evening grading profile would stain months of the lake. A CTM is
#     applied after capture, so recordings stay color-accurate.
{
  mkFeatureModule,
  lib,
  # Declared, not merely captured by the ellipsis: module args sourced from
  # `_module.args` (pkgs among them) are injected only for formals the
  # function actually names, so `...` alone leaves pkgs absent from @args and
  # configFn's own `pkgs` destructure fails at eval time.
  pkgs,
  ...
}@args:
mkFeatureModule {
  path = [
    "desktop"
    "colorTemperature"
  ];
  description = "Time-of-day display color temperature via hyprsunset CTM";
  extraOptions = {
    profiles = lib.mkOption {
      type = lib.types.listOf (
        lib.types.submodule {
          options = {
            time = lib.mkOption {
              type = lib.types.str;
              description = "HH:MM at which this profile becomes active.";
            };
            temperature = lib.mkOption {
              type = lib.types.nullOr lib.types.int;
              default = null;
              description = "Color temperature in K. Null means neutral (identity matrix).";
            };
            gamma = lib.mkOption {
              type = lib.types.nullOr lib.types.int;
              default = null;
              description = "Display gamma percentage. Null leaves it at 100%.";
            };
          };
        }
      );
      default = [
        {
          time = "07:00";
          temperature = null;
        }
        {
          time = "19:00";
          temperature = 4500;
        }
        {
          time = "22:00";
          temperature = 3600;
        }
        {
          time = "01:00";
          temperature = 3000;
          gamma = 90;
        }
      ];
      description = ''
        Time-of-day grading profiles, applied by hyprsunset's own scheduler.
        The default is a deliberately mild curve: neutral through the working
        day, a first warm step at dusk, a second after the usual wind-down
        hour, and a dim warm floor for the small hours. Temperatures below
        ~3000K are where the shift stops reading as "warm" and starts reading
        as "broken white balance", so the floor sits above that.

        Live tuning does not need a rebuild: `hyprctl hyprsunset temperature
        <K>` and `hyprctl hyprsunset identity` retarget the running daemon,
        which is the right way to find the numbers before committing them
        here.
      '';
    };
  };
  configFn =
    {
      cfg,
      config,
      lib,
      pkgs,
      user,
      ...
    }:
    let
      renderProfile =
        p:
        let
          body = lib.optional (p.temperature != null) "    temperature = ${toString p.temperature}"
            ++ lib.optional (p.temperature == null) "    identity = true"
            ++ lib.optional (p.gamma != null) "    gamma = ${toString p.gamma}";
        in
        lib.concatStringsSep "\n" ([ "profile {" "    time = ${p.time}" ] ++ body ++ [ "}" ]);
    in
    {
      sinnix.runtime.surfaces.hyprsunset = {
        unit = "hyprsunset.service";
        manager = "user";
        resourceClass = "desktop-shell";
        observe = {
          enable = true;
          restartable = true;
        };
      };

      home-manager.users.${user} =
        { ... }:
        {
          home.packages = [ pkgs.hyprsunset ];

          xdg.configFile."hypr/hyprsunset.conf".text =
            lib.concatMapStringsSep "\n\n" renderProfile cfg.profiles + "\n";

          systemd.user.services.hyprsunset = {
            Unit = {
              Description = "Time-of-day display color temperature (CTM)";
              PartOf = [ "graphical-session.target" ];
              After = [ "graphical-session.target" ];
            };
            Service = lib.sinnix.mkRuntimeServiceConfig {
              runtimeInventory = config.sinnix.runtime.inventory;
              unit = "hyprsunset.service";
              overrides = {
                ExecStart = "${pkgs.hyprsunset}/bin/hyprsunset";
                Restart = "on-failure";
              };
            };
            Install.WantedBy = [ "graphical-session.target" ];
          };
        };
    };
} args
