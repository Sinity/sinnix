{ inputs, lib, ... }:
{
  imports = [
    ./boot.nix
    ./input.nix
    ./storage.nix
    ./display.nix
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
      # Keep the host dark while still making the next rebuild exercise agenix,
      # database provisioning, and the full eventual node graph configuration.
      prepareHost = true;
      enable = false;
      provisionDatabase = true;
      activationProfile = "full";
      environment = "prod";
    };
    polylogue.enable = false;
    power-watchdog.enable = true;
    sentinel.enable = true;
  };

  systemd.services.systemd-tpm2-setup.enable = lib.mkForce false;
  systemd.services.systemd-tpm2-setup-early.enable = lib.mkForce false;
}
