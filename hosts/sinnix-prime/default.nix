{ inputs, lib, ... }:
{
  imports = [
    ./boot.nix
    ./boot-profiles.nix
    ./input.nix
    ./storage.nix
    ./display.nix
  ];

  networking.hostName = "sinnix-prime";

  # ── GPU mode ── single toggle, flip and rebuild ──────────────────────────────
  # "nvidia"      = proprietary driver, no power mgmt
  # "nvidia-open" = open NVIDIA kernel module, no power mgmt
  # "igpu"        = Intel UHD 770, discrete GPU physically absent
  sinnix.gpu.mode = "nvidia-open";
  sinnix.gpu.nvidiaTuning = {
    enable = true; # active for now; flip back to false if the tuning experiment should be disabled
    powerMizerMode = "prefer-max-performance"; # candidate way to avoid the deepest idle P-state without changing clocks directly
    fanFloorPercent = 80; # deliberately aggressive runtime floor for the current reset-avoidance experiment
    enablePersistenceDaemon = true; # keep the driver warm if/when runtime tuning experiments are enabled
  };

  sinnix.machine.isDesktop = true;

  sinnix.bundles.desktop.enable = true;
  sinnix.bundles.dev.enable = true;

  sinnix.features.cli.task-tracking.enable = true;
  sinnix.features.cli.stability-lab.enable = true;
  sinnix.features.cli.polylogue.enable = true;
  sinnix.persistence.enable = true;

  sinnix.features.dev.agentRestore.autoRestore.enable = false;

  sinnix.features.dev.editors.enable = true;
  sinnix.features.dev.editors.vscode.enable = true;
  sinnix.features.dev.editors.antigravity.enable = true;
  sinnix.services = {
    transmission.enable = true;
    terminal-capture.enable = true;
    below.enable = true;
    sinex.enable = false;
    polylogue.enable = false;
    power-watchdog.enable = true;
    sentinel.enable = true;
    reboot-no-more = {
      launchCapture.enable = false; # operational default; investigation variants live in boot profiles instead of the base host state
      enable = false; # operational default; boot specialisations re-arm the recorder when explicitly chosen
      diagnosisMode = false; # keep the default boot boring; investigation variants enable diagnosis explicitly
      diagnosisConsoleLogLevel = 4; # keep the visible console readable while /dev/kmsg still captures full recorder-side evidence
      diagnosisIgnoreLoglevel = false; # avoid pre-service debug-priority console floods from simpledrm/NVIDIA fallback paths
      diagnosisDrmDebugProfile = "atomic-kms"; # retain the useful KMS/atomic signal set
      diagnosisDrmDebugActivation = "runtime"; # arm drm.debug only after reboot-no-more has started its collectors
      diagnosisRuntimeDrmDebugSeconds = 180; # bound the debug window to the fragile display bring-up phase
      diagnosisLogBufLen = "32M"; # keep a large kernel ring so the runtime DRM window still survives long enough for triage
      diagnosisPanicNoReboot = true; # keep system alive on kernel panic instead of auto-rebooting
      elevateLoglevel = null; # do not re-raise console verbosity on startup; avoid turning runtime drm.debug back into console spam
      diagnosisDisablePcieGen3 = true; # NVIDIA comparison knob kept armed for the next dGPU boot
      ramoops = {
        enable = true;
        reserveMemmap = true; # reserve the buffer explicitly instead of pointing ramoops at ordinary DRAM and hoping
        memAddress = "0x8bf000000"; # 8 MiB reservation directly below the BIOS-reserved 0x8bf800000-0x8bfffffff RAM buffer
        memSize = "0x800000";
        recordSize = 1048576; # 1 MiB crash record
        consoleSize = 2097152; # 2 MiB console log
        pmsgSize = 524288; # 512 KiB userspace markers
        ftraceSize = 524288; # 512 KiB ftrace dump
      };
    };
  };

  systemd.services.systemd-tpm2-setup.enable = lib.mkForce false;
  systemd.services.systemd-tpm2-setup-early.enable = lib.mkForce false;
}
