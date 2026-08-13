# Opt-in ComfyUI wallpaper generation batch (bd:sinnix-s6ke.3), off by
# default and cheap to trigger: `sinnix wallpaper generate` runs it
# on-demand, or enable this service for a periodic off-hours batch.
#
# The script (scripts/sinnix-wallpaper-generate) starts ComfyUI via the
# existing `sinnix-ai` on-demand control plane, submits a small palette-
# targeted txt2img batch, screens results with the same OLED brightness/
# uniformity heuristic `sinnix-wallpaper import` uses, classifies survivors
# straight into the corpus's time-of-day/theme-mode sets
# (modules/features/desktop/wallpaper.nix), and always stops ComfyUI again
# -- even on failure -- so a triggered batch never holds the GPU past its
# own run. ComfyUI now carries a mutual systemd Conflicts= against every
# other gpu-inference backend/container (ai-control.nix, sinnix-joac), so
# systemd itself refuses a second resident GPU consumer even outside this
# script's own start/stop bracket; this stop-in-finally remains the
# well-behaved way to release the GPU promptly after a batch instead of
# relying on that as the only guard. Runs under the "gpu-runtime" resource
# class so it never serializes against builds.
{
  mkServiceModule,
  lib,
  pkgs,
  ...
}@args:
mkServiceModule {
  name = "wallpaper-generate";
  description = "Opt-in off-hours ComfyUI wallpaper generation batch";
  surface = {
    unit = "sinnix-wallpaper-generate.service";
    manager = "user";
    resourceClass = "gpu-runtime";
    observe = {
      enable = true;
      restartable = false;
    };
  };
  extraOptions = {
    onCalendar = lib.mkOption {
      type = lib.types.str;
      default = "04:30";
      description = "systemd OnCalendar for the periodic batch (kept off-hours by default).";
    };
    count = lib.mkOption {
      type = lib.types.int;
      default = 1;
      description = "Images per palette family per run.";
    };
    families = lib.mkOption {
      type = lib.types.listOf lib.types.str;
      default = [ ];
      description = ''
        Palette families to render (see `sinnix-wallpaper-generate
        --list-families`). Empty = every family the script knows about.
      '';
    };
  };
  configFn =
    {
      cfg,
      config,
      lib,
      helpers,
      pkgs,
      ...
    }:
    let
      scriptPkgs = helpers.mkSinnixPackagesFor pkgs;
      user = config.sinnix.user.name;
      familiesArg = lib.optionalString (
        cfg.families != [ ]
      ) "--families ${lib.concatStringsSep "," cfg.families}";
    in
    {
      home-manager.users.${user} = {
        home.packages = [ scriptPkgs.sinnix-wallpaper-generate ];

        systemd.user.services.sinnix-wallpaper-generate = {
          Unit.Description = "Batch-generate wallpapers via ComfyUI, palette-targeted";
          Service = {
            Type = "oneshot";
            ExecStart = "${scriptPkgs.sinnix-wallpaper-generate}/bin/sinnix-wallpaper-generate --count ${toString cfg.count} ${familiesArg}";
            # Rendering + polling for a handful of images; generous but bounded
            # so a wedged ComfyUI job doesn't hold the unit (and hence the
            # `sinnix-ai stop comfyui` cleanup in the script's finally-block)
            # open indefinitely.
            TimeoutStartSec = "45min";
          };
        };

        systemd.user.timers.sinnix-wallpaper-generate = {
          Unit.Description = "Timer for the periodic off-hours wallpaper generation batch";
          Timer = {
            OnCalendar = cfg.onCalendar;
            Persistent = false;
            RandomizedDelaySec = "10min";
            Unit = "sinnix-wallpaper-generate.service";
          };
          Install.WantedBy = [ "timers.target" ];
        };
      };
    };
} args
