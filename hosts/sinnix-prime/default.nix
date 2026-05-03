{ inputs, lib, ... }:
{
  imports = [
    ./boot.nix
    ./input.nix
    ./storage.nix
    ./display.nix
    inputs.sinex.nixosModules.default
    ../../modules/services/sinex/bridge.nix
  ];

  networking.hostName = "sinnix-prime";

  # ── GPU mode ── single toggle, flip and rebuild ──────────────────────────────
  # "nvidia"      = proprietary driver
  # "nvidia-open" = open NVIDIA kernel module
  # "igpu"        = Intel UHD 770, discrete GPU physically absent
  sinnix.gpu.mode = "nvidia-open";

  sinnix.machine.isDesktop = true;

  sinnix.bundles.desktop.enable = true;
  sinnix.bundles.dev.enable = true;

  # VR streaming to Quest 3 (WiVRn + Monado OpenXR stack + ADB tools)
  sinnix.features.desktop.vr.enable = true;

  sinnix.features.cli.task-tracking.enable = true;
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
    sinex = {
      prepareHost = true;
      enable = true;
      # Start through the delayed `sinex-runtime.target`, not during the
      # graphical boot transaction. Sinex #932 guards the worst hidden full
      # replay case; #914/#915 still track writeback/retry/metrics follow-up.
      autoStart = true;
      provisionDatabase = true;
      activationProfile = "full";
      environment = "prod";
    };
    polylogue.enable = true;
    power-watchdog.enable = true;
    network-monitor.enable = true;
    weechat-log-sealer.enable = true;
  };
  systemd.services.systemd-tpm2-setup.enable = lib.mkForce false;
  systemd.services.systemd-tpm2-setup-early.enable = lib.mkForce false;
}
