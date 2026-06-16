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
  sinnix.gpu.mode = "nvidia";

  sinnix.machine.isDesktop = true;

  # Every capability in modules/features/ is default-on; this host expresses
  # only configuration detail (subfeatures and option values), not enables.
  sinnix.features.desktop.audioCapture = {
    asrProvider = "openai";
    asrDiarization = false;
  };
  sinnix.features.dev.editors.vscode.enable = true;
  sinnix.features.dev.editors.antigravity.enable = true;

  sinnix.persistence.enable = true;
  sinnix.services = {
    agent-gateway = {
      enable = true;
      http.enable = true;
    };
    transmission = {
      enable = true;
      autoStart = true;
    };
    terminal-capture.enable = true;
    below = {
      enable = true;
      collectIntervalSec = 5;
      # Keep telemetry on /realm so the root filesystem stays slim. Same
      # subtree as machine-telemetry and activitywatch captures.
      storeDir = "/realm/data/captures/machine/below";
    };
    sinex = {
      prepareHost = true;
      enable = true;
      # Start through the delayed `sinex-runtime.target`, not during the
      # graphical boot transaction.
      autoStart = true;
      provisionDatabase = true;
      activationProfile = "full";
      environment = "prod";
      filesystem.watchPaths = [
        "/realm/project"
        "/realm/inbox/download"
      ];
    };
    polylogue.enable = true;
    machine-telemetry.enable = true;
    weechat-log-sealer.enable = true;
    airvpn-seed = {
      enable = true;
      autoStart = false;
      forwardedPort = 20241;
    };
    lynchpin = {
      enable = true;
      materializationTimer.enable = true;
    };
  };
  # This board's fTPM blocks system activation in systemd-tpm2-setup. Keep
  # TPM2 setup masked on sinnix-prime; Secure Boot key material is file-backed.
  systemd.services.systemd-tpm2-setup.enable = lib.mkForce false;
  systemd.services.systemd-tpm2-setup-early.enable = lib.mkForce false;

  # Persist the system journal on the root SSD. /realm is data/capture storage,
  # not the boot-critical journal path.
  sinnix.persistence.system.directories = [ "/var/log/journal" ];
  services.journald = {
    storage = lib.mkForce "persistent";
    extraConfig = lib.mkForce ''
      Storage=persistent
      Compress=yes
      SyncIntervalSec=2min
      # 32G bounds runaway log spam (~years at the measured ~0.3 GB/day;
      # sinexd heartbeats are ~90 % of volume). The old 128G cap was
      # effectively unbounded growth on the wear-limited root SSD.
      SystemMaxUse=32G
      SystemKeepFree=10G
      SystemMaxFileSize=128M
      MaxFileSec=1week
      MaxRetentionSec=0
      RateLimitIntervalSec=30s
      RateLimitBurst=500
      ForwardToSyslog=no
    '';
  };
}
