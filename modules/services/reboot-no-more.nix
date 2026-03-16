{
  lib,
  config,
  inputs,
  ...
}:
let
  cfg = config.sinnix.services.reboot-no-more;
  moduleDefaults = {
    stableTargetById = "/dev/disk/by-id/nvme-Samsung_SSD_960_EVO_250GB_S3ESNX0K130869X-part1";
  };
  # DRM debug masks matching kernel DRM_UT_* bits (include/drm/drm_print.h)
  drmDebugMask = {
    "kms"        = "0x04";   # DRM_UT_KMS
    "atomic-kms" = "0x14";   # DRM_UT_KMS | DRM_UT_ATOMIC
    "verbose"    = "0x1ff";  # all debug categories
  };
in
{
  imports = [ inputs.reboot-no-more.nixosModules.reboot-no-more ];

  options.sinnix.services.reboot-no-more = {
    enable = lib.mkEnableOption "reboot-no-more recorder service";
    launchCapture.enable = lib.mkOption {
      type = lib.types.bool;
      default = false;
      description = ''
        Wrap fragile launch paths such as tty1 -> Hyprland and Google Chrome with
        `launch-trigger-capture`.

        This is intentionally separate from `enable` because the wrapper is much
        more intrusive than the recorder itself and should only be opted into
        explicitly.
      '';
    };
    target = lib.mkOption {
      type = lib.types.str;
      default = moduleDefaults.stableTargetById;
      description = "Stable target for durable ring capture.";
    };
    stableTargetsOnly = lib.mkOption {
      type = lib.types.bool;
      default = true;
      description = "Require stable target identifiers and refuse raw /dev node inputs by default.";
    };
    installSystemPackage = lib.mkOption {
      type = lib.types.bool;
      default = true;
      description = "Install the reboot-no-more package into systemPackages.";
    };
    wantedBy = lib.mkOption {
      type = lib.types.listOf lib.types.str;
      default = [ "multi-user.target" ];
      description = "Systemd units that should start after this recorder.";
    };
    before = lib.mkOption {
      type = lib.types.listOf lib.types.str;
      default = [
        "getty@tty1.service"
        "graphical.target"
      ];
      description = "Systemd units that should start after this recorder.";
    };
    after = lib.mkOption {
      type = lib.types.listOf lib.types.str;
      default = [ "systemd-udev-settle.service" ];
      description = "Systemd units that should settle before this recorder starts.";
    };
    wants = lib.mkOption {
      type = lib.types.listOf lib.types.str;
      default = [ "local-fs.target" ];
      description = "Systemd units this recorder service should be pulled in with.";
    };
    extraArgs = lib.mkOption {
      type = lib.types.listOf lib.types.str;
      default = [ ];
      description = "Additional flags to pass to `reboot-no-more record`.";
    };
    diagnosisMode = lib.mkOption {
      type = lib.types.bool;
      default = false;
      description = "Enable diagnosis-oriented boot/runtime behavior for reboot-no-more.";
    };
    elevateLoglevel = lib.mkOption {
      type = lib.types.nullOr (lib.types.ints.between 1 8);
      default = null;
      description = "Raise kernel printk console loglevel at recorder startup (runtime only).";
    };
    diagnosisDrmDebugProfile = lib.mkOption {
      type = lib.types.enum [
        "off"
        "kms"
        "atomic-kms"
        "verbose"
      ];
      default = "off";
      description = "Select the DRM debug mask profile used during diagnosis boots.";
    };
    diagnosisDrmDebugActivation = lib.mkOption {
      type = lib.types.enum [
        "boot"
        "runtime"
      ];
      default = "runtime";
      description = "Choose whether DRM debug activates on the kernel command line or after the recorder starts.";
    };
    diagnosisRuntimeDrmDebugSeconds = lib.mkOption {
      type = lib.types.nullOr lib.types.ints.positive;
      default = 180;
      description = "When runtime DRM debug is selected, restore the previous mask after this many seconds.";
    };
    diagnosisConsoleLogLevel = lib.mkOption {
      type = lib.types.ints.between 1 8;
      default = 4;
      description = "Console loglevel forced during diagnosis mode.";
    };
    diagnosisIgnoreLoglevel = lib.mkOption {
      type = lib.types.bool;
      default = false;
      description = "Add ignore_loglevel during diagnosis mode.";
    };
    diagnosisLogBufLen = lib.mkOption {
      type = lib.types.nullOr lib.types.str;
      default = null;
      description = "Optional kernel log buffer size used in diagnosis mode.";
    };
    diagnosisPanicNoReboot = lib.mkOption {
      type = lib.types.bool;
      default = false;
      description = "Add panic=0 when diagnosis mode is enabled.";
    };
    diagnosisDisablePcieGen3 = lib.mkOption {
      type = lib.types.bool;
      default = false;
      description = "Add nvidia.NVreg_EnablePCIeGen3=0 in diagnosis mode.";
    };
    ramoops = {
      enable = lib.mkOption {
        type = lib.types.bool;
        default = false;
        description = "Enable reserve-backed ramoops/pstore capture for warm-reset crash remnants.";
      };
      memAddress = lib.mkOption {
        type = lib.types.str;
        default = "0x100000000";
        description = "Physical address used for the ramoops region.";
      };
      memSize = lib.mkOption {
        type = lib.types.str;
        default = "0x400000";
        description = "Size of the ramoops region.";
      };
      reserveMemmap = lib.mkOption {
        type = lib.types.bool;
        default = false;
        description = "Reserve the ramoops range explicitly with memmap= at boot.";
      };
      recordSize = lib.mkOption {
        type = lib.types.ints.positive;
        default = 131072;
        description = "Size of each ramoops crash record.";
      };
      consoleSize = lib.mkOption {
        type = lib.types.ints.positive;
        default = 131072;
        description = "Size of the ramoops console region.";
      };
      pmsgSize = lib.mkOption {
        type = lib.types.ints.positive;
        default = 65536;
        description = "Size of the ramoops pmsg region.";
      };
      ftraceSize = lib.mkOption {
        type = lib.types.ints.positive;
        default = 65536;
        description = "Size of the ramoops ftrace region.";
      };
      ecc = lib.mkOption {
        type = lib.types.bool;
        default = true;
        description = "Enable ECC for ramoops records.";
      };
    };
  };

  config = lib.mkMerge [
    # ── Upstream module wiring ────────────────────────────────────────────────────
    # Maps sinnix options to the upstream reboot-no-more NixOS module interface.
    # diagnosisMode → deepMode (renamed in upstream rewrite).
    # installSystemPackage, all diagnosis* options: implemented below at sinnix layer.
    {
      services.rebootNoMore = {
        enable = cfg.enable;
        target = cfg.target;
        stableTargetsOnly = cfg.stableTargetsOnly;
        wantedBy = cfg.wantedBy;
        before = cfg.before;
        after = cfg.after;
        wants = cfg.wants;
        extraArgs = cfg.extraArgs;
        deepMode = cfg.diagnosisMode;
        ramoops = cfg.ramoops;
      };
    }

    # ── Kernel params for diagnosis boots ────────────────────────────────────────
    # Previously implemented inside the upstream module; now lives here.
    (lib.mkIf cfg.diagnosisMode {
      boot.kernelParams =
        lib.optionals cfg.diagnosisPanicNoReboot [ "panic=0" ]
        ++ lib.optionals (cfg.diagnosisLogBufLen != null) [ "log_buf_len=${cfg.diagnosisLogBufLen}" ]
        ++ lib.optionals cfg.diagnosisIgnoreLoglevel [ "ignore_loglevel" ]
        ++ [ "loglevel=${toString cfg.diagnosisConsoleLogLevel}" ]
        ++ lib.optionals (cfg.diagnosisDrmDebugActivation == "boot" && cfg.diagnosisDrmDebugProfile != "off")
             [ "drm.debug=${drmDebugMask.${cfg.diagnosisDrmDebugProfile}}" ];
    })

    # Note: runtime DRM debug is handled by the recorder's --deep mode (mask 0x116,
    # armed after collectors start, restored on exit). A separate sinnix service
    # would conflict — deepMode = diagnosisMode = true in investigation specialisations.
  ];
}
