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

  # Interactive workstation posture: isDesktop=true plus the resource-
  # governance stack (slices, earlyoom, cache-trim timer, io.cost init, RAPL
  # caps, memory sysctls) — see modules/profiles/workstation.nix.
  sinnix.profiles.workstation.enable = true;

  # Every capability in modules/features/ is default-on; this host expresses
  # only configuration detail (subfeatures and option values), not enables.
  sinnix.features.desktop.hyprlandAnimations.enable = true;
  sinnix.features.desktop.audioCapture = {
    asrProvider = "openai";
    asrDiarization = false;
    enableAsrServer = false;
    enableAudioDaemon = false;
  };
  sinnix.features.dev.editors.vscode.enable = true;
  sinnix.features.dev.editors.antigravity.enable = true;

  sinnix.persistence.enable = true;
  sinnix.services = {
    agent-gateway = {
      enable = true;
      http = {
        enable = true;
        autoStart = false;
      };
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
      autoStart = false;
      provisionDatabase = true;
      activationProfile = "full";
      environment = "prod";
      filesystem.watchPaths = [
        "/realm/project"
        "/realm/inbox/download"
      ];
    };
    polylogue = {
      enable = true;
      embedding.enable = true;
      daemon.autoStart = true;
    };
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

    # ── Local AI platform ───────────────────────────────────────────────────
    # Weights/state live on durable /realm; everything binds 127.0.0.1 (reach
    # over Tailscale later). CUDA via per-package overrides — see
    # flake/overlay/package/local-ai.nix and the cuda-maintainers cache below.
    ollama = {
      enable = true; # LLM/VLM hub (OpenAI API :11434) + abliterated pre-pull + RAG embeddings
      autoStart = false;
    };
    litellm = {
      enable = true; # Anthropic↔OpenAI gateway :4000 — local models through Claude Code/Codex
      autoStart = false;
    };
    open-webui = {
      enable = true; # chat/RAG/voice frontend :8080
      autoStart = false;
    };
    koboldcpp.enable = true; # all-in-one offload + native image gen :5001 (on-demand)
    llama-cpp.enable = false; # opt-in raw llama-server :8081 (set .model first)
    whisper.enable = true; # speech-to-text :8090 (on-demand, auto-downloads model)
    comfyui = {
      enable = true; # SOTA image + text-to-video :8188 (container, CDI GPU)
      autoStart = false;
    };
    tts = {
      enable = true; # OpenedAI-Speech TTS bridge :8000 (container)
      autoStart = false;
    };
    # Image digests pinned and verified; enable when wanted (heavier, on-demand):
    musicgen.enable = false; # MusicGen/Bark audio toolkit (container)
    ocr.enable = false; # marker/Surya OCR (container)
  };

  # CUDA builds (ollama-cuda, koboldcpp/llama-cpp/whisper-cpp -cuda) are served
  # by this cache; without it they compile locally. Trusted at switch time.
  nix.settings.substituters = [ "https://cuda-maintainers.cachix.org" ];
  nix.settings.trusted-public-keys = [
    "cuda-maintainers.cachix.org-1:0dq3bujKpuEPMCX6U4WylrUDZ9JyUG0VpVZa7CNfq5E="
  ];
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
      # Persistent (not volatile) is deliberate, not drift: a 2026-05-22
      # decision moved this to volatile, then it was reverted because the
      # journal is now the forensic source for OOM/earlyoom kill events
      # (sinnix-fjq's kill_event capture greps this journal). 4G (down from
      # 32G) tightens the worst-case footprint on the MX500 root SSD (~104%
      # rated NAND endurance) while still holding ~weeks at the measured
      # ~0.3 GB/day volume (sinexd heartbeats are ~90% of it).
      SystemMaxUse=4G
      SystemKeepFree=10G
      SystemMaxFileSize=128M
      MaxFileSec=1week
      MaxRetentionSec=0
      RateLimitIntervalSec=30s
      RateLimitBurst=500
      ForwardToSyslog=no
    '';
  };

  # /tmp is plain root-backed btrfs on the MX500 (~104% rated NAND
  # endurance; sinnix-een). Bounded tmpfs moves routine /tmp churn (build
  # scratch, compile-server sockets, short-lived app temp files) into RAM
  # for the common case, at zero disk writes. Correction to the sinnix-een
  # bead's stated premise: zram swap is disabled on this host
  # (modules/profiles/workstation.nix, zramSwap.enable = false) — swap is a
  # file-backed overflow (hosts/sinnix-prime/storage.nix). As of 2026-07-09
  # that swapfile moved off the root SSD onto /realm (NVMe, not
  # wear-sensitive), so evicted tmpfs pages landing in swap no longer add
  # wear to the worn disk. This is still a net win regardless: normal
  # desktop use has ~13GiB available RAM headroom (measured 2026-07-06), a
  # 6G tmpfsSize cap keeps worst-case swap pressure bounded, and
  # drainSwapfile already evicts resident swap opportunistically.
  # Heavy/large scratch already belongs on /realm/tmp per policy, not /tmp,
  # so this tmpfs is sized for routine small-file churn, not build output.
  boot.tmp.useTmpfs = true;
  boot.tmp.tmpfsSize = "6G";
}
