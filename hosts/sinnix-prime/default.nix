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

  sinnix.bundles.desktop.enable = true;
  sinnix.bundles.dev.enable = true;

  # VR streaming to Quest 3 (WiVRn + Monado OpenXR stack + ADB tools)
  sinnix.features.desktop.vr.enable = true;
  sinnix.features.desktop.activitywatch.enable = true;
  sinnix.features.desktop.audioCapture = {
    enable = true;
    asrProvider = "openai";
    asrDiarization = false;
  };
  sinnix.features.desktop.agentVerifyTimer.enable = true;
  sinnix.features.desktop.hyprlandAnimations.enable = true;

  sinnix.features.cli.task-tracking.enable = true;
  sinnix.features.cli.polylogue.enable = true;
  sinnix.features.cli.yt-polisher.enable = true;
  sinnix.persistence.enable = true;

  sinnix.features.dev.editors.enable = true;
  sinnix.features.dev.editors.vscode.enable = true;
  sinnix.features.dev.editors.antigravity.enable = true;
  sinnix.services = {
    transmission = {
      enable = true;
      autoStart = true;
    };
    terminal-capture.enable = true;
    below = {
      enable = true;
      collectIntervalSec = 5;
      pressureWatch.enable = true;
    };
    sinex = {
      prepareHost = true;
      enable = true;
      # Start through the delayed `sinex-runtime.target`, not during the
      # graphical boot transaction. Sinex #932 guards the worst hidden full
      # replay case; #914/#915 still track writeback/retry/metrics follow-up.
      autoStart = false;
      provisionDatabase = true;
      activationProfile = "full";
      environment = "prod";
    };
    polylogue = {
      enable = true;
      daemon.autoStart = true;
    };
    hermes = {
      enable = true;
      approvals.mode = "off";
    };
    machine-telemetry = {
      enable = true;
      intervalSec = 60;
      serviceIntervalSec = 60;
      networkIntervalSec = 0;
      bufferbloatIntervalSec = 0;
      gpuIntervalSec = 0;
    };
    weechat-log-sealer.enable = true;
    # Disabled until the remote connector path has explicit auth and exposure
    # discipline. The service module remains available for a future ChatGPT
    # Web UI connector setup.
    chatgpt-mcp.enable = false;
    airvpn-seed = {
      enable = false;
      autoStart = false;
      forwardedPort = 20241;
    };
  };
  # why mkForce: this board's fTPM hangs the systemd-tpm2-setup unit on
  # activation (kernel d-state up to 30s). lanzaboote / boot defaults
  # would re-enable it; this host opts out unconditionally.
  systemd.services.systemd-tpm2-setup.enable = lib.mkForce false;
  systemd.services.systemd-tpm2-setup-early.enable = lib.mkForce false;

  # Recovery posture after repeated NVMe/Btrfs D-state stalls on /realm:
  # keep the host interactive first. These services are useful, but they
  # should not be boot-critical while /realm is producing write timeouts.
  services.journald = {
    storage = lib.mkForce "volatile";
    extraConfig = lib.mkForce ''
      Storage=volatile
      Compress=yes
      SyncIntervalSec=5min
      RuntimeMaxUse=512M
      RuntimeKeepFree=256M
      RateLimitIntervalSec=30s
      RateLimitBurst=500
      ForwardToSyslog=no
    '';
  };
  # Keep heavyweight snapshot/backup automation manual while storage is under
  # observation; lighter diagnostic timers are restored above by their modules.
  systemd.timers = {
    btrfs-metadata-image-backup.wantedBy = lib.mkForce [ ];
    btrbk.wantedBy = lib.mkForce [ ];
    borgbackup-job-realm.wantedBy = lib.mkForce [ ];
    borgbackup-job-persist.wantedBy = lib.mkForce [ ];
    borgbackup-check.wantedBy = lib.mkForce [ ];
    borgbackup-root-snapshots.wantedBy = lib.mkForce [ ];
    sinnix-borg-drill.wantedBy = lib.mkForce [ ];
  };
}
