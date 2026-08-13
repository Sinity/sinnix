# Time-of-day color temperature grading via hyprsunset (CTM, not a shader).
#
# MECHANISM CHOICE (sinnix-s6ke.1, measured 2026-08-13 on the live host, not
# inferred). The obvious vehicle for time-of-day grading is hyprshade driving
# `decoration:screen_shader`, and that is what the bead assumed. It does not
# hold up here:
#
#   - Applying hyprshade's blue-light-filter (2600K, strength 1.0) through
#     `hyprctl keyword decoration:screen_shader` changed the composited output
#     by 0.08% -- screencopy blue-channel mean 78.09 -> 78.03 on identical
#     static content. A 2600K filter should pull blue down by roughly 40%.
#   - Its GPU cost was likewise unmeasurable: 96 interleaved 1Hz samples
#     (ABAB, to cancel drift from llama-server and the screen-recorder) gave
#     77.56W shader-off vs 78.73W shader-on at 4K120 with continuous
#     full-screen damage, and identical SM occupancy. A real per-pixel pass
#     over 8.3M pixels at 120Hz is not free; "free" means it did not run.
#   - This host runs `cm = "hdr"` on the FO48U with `render:non_shader_cm = 3`
#     -- Hyprland performing color management through the hardware pipeline
#     rather than a fragment shader. The screen-shader stage is not on that
#     path.
#
# hyprsunset instead applies a color transform matrix through
# `hyprland-ctm-control-v1`, which is the interface Hyprland's own
# `render:non_shader_cm_interop` option exists to describe ("non_shader_cm
# interaction with ctm proto (hyprsunset and similar)"). Verified live: it
# negotiated ctm-control v2, bound the DP-3 output, and applied the computed
# matrix. Three consequences that matter beyond "it works":
#
#   - Zero GPU cost by construction. The transform happens in the display
#     pipeline at scanout, not in a per-pixel composite pass.
#   - It does not tint captures. A screen shader sits in the composite path,
#     so screenshots and the capture-screen recordings inherit its color --
#     an evening grading profile would quietly stain months of the lake.
#     A CTM is applied after capture, so recordings stay color-accurate
#     while the operator's eyes get the warm grading.
#   - It composes with HDR rather than fighting it, which is the whole
#     reason the shader route failed.
#
# The gimmick-tier shader catalog (CRT, matrix, cyberpunk) is not adopted
# here and, on this display configuration, could not be even if it were
# wanted -- the shader stage those depend on is inert while HDR is on.
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
            Service = {
              ExecStart = "${pkgs.hyprsunset}/bin/hyprsunset";
              Restart = "on-failure";
            };
            Install.WantedBy = [ "graphical-session.target" ];
          };
        };
    };
} args
