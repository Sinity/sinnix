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
  # governance stack (slices, earlyoom, io.cost init, RAPL caps, memory
  # sysctls) — see modules/profiles/workstation.nix.
  sinnix.profiles.workstation.enable = true;

  # Every capability in modules/features/ is default-on; this host expresses
  # only configuration detail (subfeatures and option values), not enables.
  sinnix.features.desktop.hyprlandAnimations.enable = true;
  sinnix.features.dev.editors.vscode.enable = true;
  sinnix.features.dev.editors.antigravity.enable = true;

  sinnix.persistence.enable = true;
  sinnix.services = {
    agent-gateway = {
      enable = true;
      tunnel = {
        enable = true;
        approvedManifestHash = "7078f104e482052bd0f2f3728a3beb1eaba3985a3895962ca553562c0e2aa3a5";
        tunnelId = "tunnel_6a2eb972c3bc8191be437670f455ebd9";
      };
    };
    ops-reducer.enable = true;
    transmission = {
      enable = true;
      autoStart = true;
    };
    terminal-capture.enable = true;
    # Remote access over the tailnet (sinnix-is8, enabled 2026-08-12).
    # tag:workstation must be authorized in the tailnet ACL tagOwners; the
    # auth key lives in agenix (tailscale-authkey). Plain node: no exit-node
    # or subnet-router role (deliberate).
    tailscale = {
      enable = true;
      tags = [ "tag:workstation" ];
      # Zero-blast-radius posture (operator burned by tailscale-owned DNS
      # before): never touch DNS -- the router stays DNS authority -- and
      # accept/advertise no routes. The join adds only the tailscale0
      # interface + 100.64/10 peer routes; rollback = stop tailscaled.
      enableMagicDNS = false;
      useRoutingFeatures = "none";
    };
    # Browser front door to the estate: reports, the reducer's current-state
    # dashboard, and the AI control panel. Binds loopback plus the tailscale0
    # address only, and its ports are opened on tailscale0 alone -- the LAN
    # never sees it. Depends on tailscale above (asserted in the module).
    hub.enable = true;
    # ── Capture-machinery program (2026-08-12) ──────────────────────────────
    capture-notifications.enable = true;
    capture-mpris.enable = true;
    capture-clipboard.enable = true;
    capture-primary.enable = true;
    capture-a11y.enable = true;
    capture-audio.enable = true;
    # Phase 3a (sinnix-9pd): per-window screen frames + the always-on
    # replay ring, promoted to default-on via this host enable per the
    # mkServiceModule factory contract (services are default-off at the
    # module level; hosts express the opt-in) rather than baking a
    # non-standard default into the factory itself.
    capture-screen.enable = true;
    capture-replay = {
      enable = true;
      # Single panel on this host; gsr needs the connector name (see the
      # target option's description for why "focused" cannot work).
      target = "DP-3";
    };
    capture-kitty-scrollback.enable = true;
    # Room air quality from the Awair Element's local API (sinnix-agp8) --
    # the first capture lane covering the environment rather than the machine.
    capture-awair.enable = true;
    # AORUS FO48U DDC/CI sensor poll (sinnix-70eq): power state, brightness/
    # contrast drift, input source -- turns "is the screen on" into a
    # measurement instead of an inference.
    capture-monitor.enable = true;
    # Router telemetry pulled from prime on a timer (sinnix-zihb): syslog
    # deltas, DHCP leases, wifi associations with signal, and nlbwmon's
    # seven months of per-device bandwidth. Nothing runs on the router.
    capture-router.enable = true;
    url-ledger.enable = true;
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
      # The promoted archive lives on the realm NVMe volume, not in the
      # impermanent home-directory default.
      dataDir = "/realm/state/polylogue";
      # 2026-07-21 (polylogue-dcz5/04kl): embedding OFF until the 777K-vector
      # content-hash rescue lands — the rebuilt embeddings tier is empty and
      # daemon catch-up would re-embed the whole corpus through the paid
      # Voyage API. Re-enable after polylogue-04kl executes.
      embedding.enable = false;
      daemon.autoStart = true;
    };
    machine-telemetry.enable = true;
    weechat-log-sealer.enable = true;
    # Backstop reaper for orphaned per-checkout sinex dev-postgres instances
    # (primary cleanup is sinnix-direnvrc's owner-watcher). See sinex-grlv.
    sinex-dev-db-reaper.enable = true;
    # Pre-build + cachix-push sinex whenever its pinned input moves, off the
    # interactive switch critical path. See sinnix-m9v.
    sinex-cache-prebuild.enable = true;
    # Keep the optional AirVPN tunnel inactive; Transmission uses the normal
    # host network and the router's existing 51413 port forward.
    airvpn-seed.enable = false;
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
    # llama-server :8081 serving the local reranker (/v1/rerank — an API
    # ollama does not provide). 0.6b Q8 rides fully in VRAM next to other
    # models; the 4B Q4 GGUF sits on disk as the quality-tier swap.
    # Weekly evidence-joined usage census (bead sinnix-yfr).
    census.enable = true;
    llama-cpp = {
      enable = true;
      model = "qwen3-reranker-0.6b-q8_0.gguf";
      extraFlags.reranking = true;
    };
    kokoro.enable = true; # Kokoro-82M TTS :8880 (CPU, on-demand) — replaces edge-tts
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

  # Hard memory ceiling for the collapsed sinexd daemon (event_engine + API +
  # automata + hosted source bindings all run in one systemd unit, governed
  # by exactly this resource block per nixos/modules/sources.nix). The
  # upstream default only sets a soft MemoryHigh=8G throttle; memoryMax is
  # null (uncapped) unless set here. A bulk re-import (the exact shape of the
  # Phase C rebuild) is the highest-memory-pressure workload sinexd runs, so
  # an unbounded leak/backlog spike would otherwise compete with Postgres for
  # all 32G of host RAM until host-level earlyoom intervenes instead of a
  # clean systemd-scoped restart. 14G leaves headroom for Postgres/NATS/the
  # rest of the workstation stack on this 32G host (sinex-audit-nomemcap).
  services.sinex.core.api.resources.memoryMax = "14G";

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

  # Long-term journal on the /realm NVMe (2026-07-10, operator decision):
  # the old posture (4G on the persisted MX500 root) was a wear compromise
  # capping retention at ~2 weeks. The NVMe has no wear flag, btrfs zstd:3
  # compresses journal files well beyond journald's per-field compression,
  # and the operator wants long retention: 64G size cap, 365-day time cap.
  # The nested subvol /realm/state/journal keeps journal churn out of the
  # /realm btrbk→borg snapshots (sinex's syslog capture is the durable
  # journal archive; this is the queryable window). Early boot: journald
  # runs volatile in /run until realm mounts, then
  # systemd-journal-flush.service moves logs over — the standard sequence.
  fileSystems."/var/log/journal" = {
    device = "/realm/state/journal";
    fsType = "none";
    options = [
      "bind"
      "nofail"
    ];
    depends = [ "/realm" ];
  };
  services.journald = {
    storage = lib.mkForce "persistent";
    extraConfig = lib.mkForce ''
      Storage=persistent
      Compress=yes
      SyncIntervalSec=2min
      # Persistent (not volatile) is deliberate, not drift: the journal is
      # the forensic source for OOM/earlyoom kill events (sinnix-fjq's
      # kill_event capture greps it). Retention is time-based (~1 year);
      # the size cap is a backstop, not a preallocation. Interim posture:
      # once sinex is trusted as the durable journal archive this local
      # window shrinks back to weeks and the duplication ends.
      # History/evidence: bd show sinnix-u63, bd show sinnix-fjq
      MaxRetentionSec=365day
      SystemMaxUse=64G
      SystemKeepFree=200G
      SystemMaxFileSize=128M
      MaxFileSec=1week
      RateLimitIntervalSec=30s
      RateLimitBurst=500
      ForwardToSyslog=no
    '';
  };

  # /tmp is plain root-backed btrfs on the MX500 (wear-limited). Bounded
  # tmpfs moves routine /tmp churn (build scratch, compile-server sockets,
  # short-lived app temp files) into RAM for the common case at zero disk
  # writes; any evicted pages land on the NVMe swap tier, not the worn root
  # SSD. Heavy/large scratch belongs on /realm/tmp per policy, not here —
  # this tmpfs is sized for routine small-file churn, not build output.
  # History/evidence: bd show sinnix-een
  boot.tmp.useTmpfs = true;
  boot.tmp.tmpfsSize = "6G";
}
