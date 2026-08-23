{
  inputs,
  lib,
  pkgs,
  ...
}:
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
  sinnix.features.dev.editors.vscode.enable = true;
  sinnix.features.dev.editors.antigravity.enable = true;

  sinnix.persistence.enable = true;
  sinnix.services = {
    sinnixd.enable = true;
    agent-gateway = {
      enable = true;
      tunnel = {
        enable = true;
        # Review checkpoint on what reaches remote ChatGPT. This V3 observer
        # manifest was regenerated from the packaged gateway on 2026-08-22.
        # It contains only read-annotated tools, including bounded content,
        # opaque-artifact reads, V3 status, catalog, canonical get, checkout selection,
        # and route preflight.
        approvedManifestHash = "026ce1d679a5eeb6eb866937ba067e12f3b17a453734b37e460177c9f0e2bc8e";
        approvedActionCatalogHash = "12749fedc7b71bc3fe096fafd8eab3953fdfe6d5e3e5c4111b8ee3aa254af4cd";
        tunnelId = "tunnel_6a2eb972c3bc8191be437670f455ebd9";
      };
    };
    ops-reducer.enable = true;
    # Clodex remains inactive until its one-time device-code OAuth has created
    # ~/.clodex/providers.json. See docs/clodex.md.
    clodex.enable = true;
    # Band data from Xiaomi's cloud, beside the phone's Health Connect lane.
    # A capture lane, so it is on and stays on (the login token lives in
    # /realm/state/xiaomi-witness; re-login is agent-drivable through the
    # operator's browser session).
    xiaomi-witness.enable = true;
    transmission = {
      enable = true;
      autoStart = true;
    };
    terminal-capture.enable = true;
    # Remote access over the tailnet. tag:workstation must be authorized in the
    # tailnet ACL tagOwners; the auth key lives in agenix (tailscale-authkey).
    # Plain node: no exit-node or subnet-router role.
    tailscale = {
      enable = true;
      tags = [ "tag:workstation" ];
      # Zero-blast-radius posture: never touch DNS -- the router stays DNS
      # authority -- and accept/advertise no routes, so the join adds only the
      # tailscale0 interface + 100.64/10 peer routes.
      enableMagicDNS = false;
      useRoutingFeatures = "none";
    };
  };

  # Mosh server, tailscale0-scoped only, for phone-as-client sessions into this
  # always-on desktop. Server side only: no mosh on the phone, because
  # scripts/sinnix-phone drives the desktop->phone direction and Mosh does not
  # help it (rsync still needs SSH transport, Mosh has no scripted/batch mode,
  # and a sleeping phone-as-server breaks SSH and Mosh equally).
  environment.systemPackages = [ pkgs.mosh ];
  networking.firewall.interfaces.tailscale0.allowedUDPPortRanges = [
    {
      from = 60000;
      to = 61000;
    }
  ];

  sinnix.services = {
    # Browser front door to the system: reports, the reducer's current-state
    # dashboard, and the AI control panel. Binds loopback plus the tailscale0
    # address only, and its ports are opened on tailscale0 alone -- the LAN
    # never sees it. Depends on tailscale above (asserted in the module).
    hub.enable = true;
    # ── Capture machinery ───────────────────────────────────────────────────
    capture-notifications.enable = true;
    capture-mpris.enable = true;
    capture-clipboard.enable = true;
    capture-primary.enable = true;
    capture-a11y.enable = true;
    capture-audio.enable = true;
    # Per-window screen frames. The always-on replay ring is off: on the
    # 2026-08-14 reboot it was the only user unit to miss its stop timeout,
    # and its SIGKILL at the 90s mark is the log line that immediately
    # unblocked the graphical session target, Hyprland, and ~30 other units
    # that had piled up behind it -- one stuck recorder, the whole reboot.
    # Set against that: the ring has produced exactly one saved clip since
    # it was introduced, so it was costing a minute and a half of every
    # reboot for a feature that is not being used. Re-enable when the
    # save-on-hotkey path is something the day actually reaches for.
    capture-screen.enable = true;
    capture-replay = {
      enable = false;
      # Single panel on this host; gsr needs the connector name (see the
      # target option's description for why "focused" cannot work).
      target = "DP-3";
    };
    capture-kitty-scrollback.enable = true;
    # Room air quality from the Awair Element's local API.
    capture-awair.enable = true;
    # Logitech battery/DPI + BT audio (AVRCP volume/codec) + BT battery
    # (GATT 0x180f / bluez Battery1, requires the Experimental interface
    # flip in networking.nix). bt-battery only ever populates when the
    # Buds2Pro are actually connected -- the other paired devices are
    # classic-BT-only for GATT purposes.
    capture-peripherals.enable = true;
    # Spotify recently-played listening history. Live now even though the
    # refresh token doesn't exist yet -- the unit fails its own poll with a
    # one-line instruction ("run sinnix spotify-auth") until the operator
    # completes that one interactive bootstrap, so the lane goes live the
    # moment the token lands with no further config change.
    capture-spotify.enable = true;
    # AORUS FO48U DDC/CI sensor poll: power state, brightness/contrast drift,
    # input source.
    capture-monitor.enable = true;
    # L0 network flow metadata via kernel conntrack events: 5-tuple +
    # byte/packet counters, no packet capture, no TLS interception.
    capture-netflow.enable = true;
    # The phone's system log, pulled over adb because READ_LOGS is not a
    # permission a sideloaded app can hold. Everything else the phone produces
    # it pushes itself -- see docs/phone.md.
    phone-logcat.enable = true;
    # The other half of the phone's hold-still instruments (score the traces
    # the app uploads: pulse, tremor, sway, interoception, voice) and the
    # persistent phone->prime telemetry push both used to be separate
    # opt-in services here. As of 2026-08-17 (sinnix-tjqi) both live inside
    # sinnix-phone-dispatcher, which runs whenever hub.enable does (above) --
    # there is no separate toggle left to set.
    # Router telemetry pulled from prime on a timer: syslog deltas, DHCP
    # leases, wifi associations with signal, and nlbwmon per-device bandwidth.
    # Nothing runs on the router.
    capture-router.enable = true;
    url-ledger.enable = true;
    # Weekly re-walk of /realm and /outer-realm into the queryable
    # inventory/content/judgment-ledger index at data/derived/inventory.
    # Was a manual one-shot from 2026-08-16 until this; see fs-index.nix.
    fs-index.enable = true;
    # Daily run at the Xiaomi quota reset (sinnix-9tc). Self-terminating:
    # stops for good once the unlock is granted. Disabled 2026-08-19: the
    # parallel HyperOS account-bind route (sinnix-9tc.1) succeeded directly
    # (applyBind code 0), making this daily Community-quota lottery
    # redundant. Both routes only reach the ordinary 168h+ Mi Unlock wait,
    # not the bootloader unlock itself.
    mi-unlock.enable = false;
    # Video special-case over the ledger: yt-dlp resolves video-hosting URLs
    # into a real archived copy. Wayback/Common Crawl CDX coverage does not
    # preserve video.
    video-resolve.enable = true;
    below = {
      enable = true;
      collectIntervalSec = 5;
      # Keep telemetry on /realm so the root filesystem stays slim. Same
      # subtree as machine-telemetry and activitywatch captures.
      storeDir = "/realm/data/machine/below";
    };
    sinex = {
      prepareHost = true;
      enable = true;
      # Start through the delayed `sinex-runtime.target`, not during the
      # graphical boot transaction.
      autoStart = false;
      provisionDatabase = true;
      # A bounded daily-use trial: Atuin terminal history reaches
      # sinex_search_events without enabling the full workstation capture and
      # automata graph. The delayed timer stays inert until this loop has
      # survived its one-week observation window.
      activationProfile = "user-mile";
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
      # Embedding stays off until the content-hash rescue lands: the rebuilt
      # embeddings tier is empty, so daemon catch-up would re-embed the whole
      # corpus through the paid Voyage API.
      embedding.enable = false;
      # Every launch dies on DurableChangeTrainError (archive identity vs
      # historical train), and Restart=on-failure turns that into a restart
      # loop. Nothing is lost by parking it: the Claude/Codex hooks spool
      # independently and get ingested when it can run again. Staying down is
      # currently a decision rather than a defect -- see the surface's
      # acknowledgement in modules/services/polylogue.nix for the mechanism,
      # the landed-but-unpinned fix, and the freeze that gates the restart
      # (sinnix-qh6s, sinnix-8f6y).
      daemon.autoStart = false;
    };
    machine-telemetry.enable = true;
    # Operator steering: store + rituals + read-only cockpit at
    # http://127.0.0.1:8791.
    steering.enable = true;
    # Periodic state-dump -> claude -p (enrichment-pass skill) -> versioned
    # derived outputs.
    #
    # PAUSED (temporary, operator call 2026-08-17): the hourly Opus pass
    # burns ~500k tokens a run — 12–18M/day of subscription quota — and the
    # first measured day made that visible. Re-enable as-is, or with a
    # cheaper model / longer cadence, once the quota tradeoff is decided.
    enrichment-loop.enable = false;
    # Kernel audit capture plus the check that no unit is sandboxed out of
    # writing its own declared output.
    sandbox-audit.enable = true;
    weechat-log-sealer.enable = true;
    # Backstop reaper for orphaned per-checkout sinex dev-postgres instances;
    # primary cleanup is sinnix-direnvrc's owner-watcher.
    sinex-dev-db-reaper.enable = true;
    # Pre-build + cachix-push sinex whenever its pinned input moves, off the
    # interactive switch critical path.
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
    # llama-server :8081 serving the local reranker (/v1/rerank — an API ollama
    # does not provide). 0.6b Q8, bounded ctx-size (see
    # modules/services/llama-cpp.nix); the 4B Q4 GGUF sits on disk as the
    # quality-tier swap. gpuLayers = 0 is not zero VRAM: the CUDA-linked binary
    # still holds a few hundred MiB of context/compute-buffer even with
    # --n-gpu-layers 0, released on exit. Socket-activated on demand but
    # deliberately outside the gpu-inference admission mesh
    # (modules/services/ai-control.nix), so it coexists with a resident
    # ollama/koboldcpp session instead of making every retrieval turn
    # pay a GPU reload.
    # Weekly evidence-joined usage census.
    census.enable = true;
    llama-cpp = {
      enable = true;
      model = "qwen3-reranker-0.6b-q8_0.gguf";
      gpuLayers = 0;
      extraFlags.reranking = true;
    };
    muse-glimmer = {
      enable = true;
      model = "muse-glimmer-30B-kquant-17gb.gguf";
    };
    kokoro.enable = true; # Kokoro-82M TTS :8880 (CPU, on-demand) — replaces edge-tts
    stt.enable = true; # speech-to-text :8090 — Parakeet TDT, CPU-only, on-demand
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
  # automata + hosted source bindings all run in one systemd unit, governed by
  # exactly this resource block per nixos/modules/sources.nix). Upstream sets
  # only a soft MemoryHigh=8G throttle and leaves memoryMax null, so without
  # this a leak or bulk-import backlog competes with Postgres for all 32G until
  # host earlyoom fires instead of a clean systemd-scoped restart. 14G leaves
  # headroom for Postgres/NATS and the rest of the stack on this 32G host.
  services.sinex.core.api.resources.memoryMax = "14G";

  # CUDA builds (ollama-cuda, koboldcpp/llama-cpp -cuda) are served
  # by this cache; without it they compile locally. Trusted at switch time.
  nix.settings.substituters = [ "https://cuda-maintainers.cachix.org" ];
  nix.settings.trusted-public-keys = [
    "cuda-maintainers.cachix.org-1:0dq3bujKpuEPMCX6U4WylrUDZ9JyUG0VpVZa7CNfq5E="
  ];
  # This board's fTPM blocks system activation in systemd-tpm2-setup. Keep
  # TPM2 setup masked on sinnix-prime; Secure Boot key material is file-backed.
  systemd.services.systemd-tpm2-setup.enable = lib.mkForce false;
  systemd.services.systemd-tpm2-setup-early.enable = lib.mkForce false;

  # Long-term journal on the /realm NVMe rather than the wear-limited MX500
  # root, so retention can be generous (64G size cap, 365-day time cap). The
  # nested subvol /realm/state/journal keeps journal churn out of the /realm
  # btrbk→borg snapshots; sinex's syslog capture is the durable archive and
  # this is the queryable window.
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
    # Set through the options rather than repeated in extraConfig below.
    # NixOS emits its own RateLimitInterval=/RateLimitBurst= lines from these,
    # so restating them in extraConfig produced a journald.conf carrying each
    # key twice with DIFFERENT values (burst 10000 then 500) plus the
    # deprecated RateLimitInterval= spelling. Last-wins resolved it, but
    # nothing readable said which value was in force.
    rateLimitInterval = lib.mkForce "30s";
    rateLimitBurst = lib.mkForce 500;
    extraConfig = lib.mkForce ''
      Compress=yes
      SyncIntervalSec=2min
      # Persistent (not volatile) is deliberate: the journal is the forensic
      # source for OOM/earlyoom kill events, which the kill_event capture
      # greps out of it. Retention is time-based; the size cap is a backstop,
      # not a preallocation.
      MaxRetentionSec=365day
      SystemMaxUse=64G
      SystemKeepFree=200G
      SystemMaxFileSize=128M
      MaxFileSec=1week
      ForwardToSyslog=no
    '';
  };

  # /tmp is plain root-backed btrfs on the MX500 (wear-limited). Bounded
  # tmpfs moves routine /tmp churn (build scratch, compile-server sockets,
  # short-lived app temp files) into RAM for the common case at zero disk
  # writes; any evicted pages land on the NVMe swap tier, not the worn root
  # SSD. Heavy/large scratch belongs on /realm/tmp per policy, not here —
  # this tmpfs is sized for routine small-file churn, not build output.
  boot.tmp.useTmpfs = true;
  boot.tmp.tmpfsSize = "6G";
}
