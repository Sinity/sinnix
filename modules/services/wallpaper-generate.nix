# Opt-in ComfyUI wallpaper generation batch, off by default and cheap to
# trigger: `sinnix wallpaper generate` runs it on-demand, or enable this
# service for a periodic off-hours batch.
#
# The script (scripts/sinnix-wallpaper-generate) starts ComfyUI via the
# `sinnix-ai` on-demand control plane, submits a small palette-targeted
# txt2img batch, screens results with the same OLED brightness/uniformity
# heuristic `sinnix-wallpaper import` uses, classifies survivors into the
# corpus's time-of-day/theme-mode sets
# (modules/features/desktop/wallpaper.nix), and always stops ComfyUI again --
# even on failure -- so a triggered batch never holds the GPU past its own
# run. Runs under the "gpu-runtime" resource class so it never serializes
# against builds.
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
  # `home.packages` is a home-manager-only concept (the operator's shell
  # profile), not a unit boilerplate concern, so it stays here rather than
  # moving into the job. Persistent=false is dropped from the timer: the
  # factory only ever emits `Persistent=true` (or omits the key), and
  # omitting it is systemd's own default of false, so this is a cosmetic
  # diff, not a behavior change. The timer's own Description= is also
  # dropped -- the factory's generated timer body carries no description
  # field, unlike the hand-written one it replaces.
  configFn =
    {
      config,
      helpers,
      pkgs,
      ...
    }:
    {
      home-manager.users.${config.sinnix.user.name}.home.packages = [
        (helpers.mkSinnixPackagesFor pkgs).sinnix-wallpaper-generate
      ];
    };
  job =
    {
      cfg,
      lib,
      helpers,
      pkgs,
      ...
    }:
    let
      scriptPkgs = helpers.mkSinnixPackagesFor pkgs;
      familiesArg = lib.optionalString (
        cfg.families != [ ]
      ) "--families ${lib.concatStringsSep "," cfg.families}";
    in
    {
      description = "Batch-generate wallpapers via ComfyUI, palette-targeted";
      manager = "user";
      execStart = "${scriptPkgs.sinnix-wallpaper-generate}/bin/sinnix-wallpaper-generate --count ${toString cfg.count} ${familiesArg}";
      serviceConfig = {
        # Rendering + polling for a handful of images; generous but bounded
        # so a wedged ComfyUI job doesn't hold the unit (and hence the
        # `sinnix-ai stop comfyui` cleanup in the script's finally-block)
        # open indefinitely.
        TimeoutStartSec = "45min";
      };
      timer = {
        onCalendar = cfg.onCalendar;
        randomizedDelaySec = "10min";
      };
    };
} args
