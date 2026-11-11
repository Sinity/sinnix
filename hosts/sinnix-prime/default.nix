{
  inputs,
  config,
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

  # SSH and Mosh retain their emergency access grant without publishing the
  # authorized client identity in the system configuration.
  services.openssh.authorizedKeysFiles = lib.mkAfter [ "/run/sinnix/authorized_keys/%u" ];

  # ── GPU mode ── single toggle, flip and rebuild ──────────────────────────────
  # "nvidia"      = proprietary driver
  # "nvidia-open" = open NVIDIA kernel module
  # "igpu"        = Intel UHD 770, discrete GPU physically absent
  sinnix.gpu.mode = "nvidia";

  # Desktop features and workstation resource policy follow the default
  # isDesktop=true machine role. Keep only host-specific choices here.
  sinnix.features.dev.editors.vscode.enable = true;
  sinnix.features.dev.editors.antigravity.enable = true;
  # Agent lanes create a Cargo target per short-lived worktree (36 on
  # 2026-11-01). Each costs ~5 GB beyond its reflinked seed, so idle targets
  # go after three days and earlier while Realm is fuller than 88%.
  sinnix.features.dev.languages.cargoCache = {
    maxIdleDays = 3;
    maxFilesystemUsePercent = 88;
  };

  sinnix.persistence.enable = true;
  sinnix.services = {
    agent-gateway = {
      enable = true;
      tunnelId = "tunnel_6a2eb972c3bc8191be437670f455ebd9";
    };
    # Clodex remains inactive until its one-time device-code OAuth has created
    # ~/.clodex/providers.json. See docs/clodex.md.
    clodex.enable = true;
    # US-only OpenAI egress lane: ChatGPT desktop, default Codex and
    # OpenAI/ChatGPT browser origins only. Other traffic remains direct.
    proton-openai.enable = true;
    # Band data from Xiaomi's cloud, beside the phone's Health Connect lane.
    # A capture lane, so it is on and stays on (the login token lives in
    # /realm/state/xiaomi-witness; re-login is agent-drivable through the
    # operator's browser session).
    capture-xiaomi-cloud.enable = true;
    # Receive phone photos and videos directly into the personal lake over
    # tailscale0. Peer/folder identities are promoted to declarative config
    # after the Android client generates its fresh device ID.
    syncthing-media.enable = true;
    transmission = {
      enable = true;
      autoStart = true;
    };
    # Remote access over the tailnet. tag:workstation must be authorized in the
    # tailnet ACL tagOwners; the auth key lives in agenix (tailscale-authkey).
    # Plain node: no exit-node or subnet-router role.
    tailscale = {
      enable = true;
      tags = [ "tag:workstation" ];
      # Zero-blast-radius setup: never touch DNS -- the router stays DNS
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
    # Browser entry point to the system: reports, the hub server's current-state
    # dashboard, and the AI control panel. Binds loopback plus the tailscale0
    # address only, and its ports are opened on tailscale0 alone -- the LAN
    # never sees it. Depends on tailscale above (asserted in the module).
    hub.enable = true;
    # ── Capture machinery ───────────────────────────────────────────────────
    # Room air quality from the Awair Element's local API.
    capture-awair.enable = true;
    # Logitech battery/DPI + BT audio (AVRCP volume/codec) + BT battery
    # (GATT 0x180f / bluez Battery1, requires the Experimental interface
    # flip in networking.nix). bt-battery only ever populates when the
    # Buds2Pro are actually connected -- the other paired devices are
    # classic-BT-only for GATT purposes.
    capture-peripherals.enable = true;
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
    below = {
      # Keep telemetry on /realm so the root filesystem stays slim. Same
      # subtree as machine-telemetry and activitywatch captures.
      storeDir = "/realm/state/below";
    };
    sinex = {
      enable = true;
      # The deployment before the rewrite, kept whole under a dated name:
      # its PostgreSQL cluster (postgresql/18, cleanly shut down), its content
      # store and its runtime state (spools, event engine state). Nothing
      # writes it, so the sinex-blobs Borg job archives the whole directory
      # by plain file copy; the cluster has no other copy.
      retainedStores = [ "/var/lib/sinex/old-2026-10-26" ];
    };
    polylogue = {
      enable = true;
      # The Python archive lives on the realm NVMe volume, not in the
      # impermanent home-directory default.
      dataDir = "/realm/state/polylogue";
    };
    # Disposable PostgreSQL for Polylogue and Sinex development (devkit).
    devkit-pg.enable = true;
    lynchpin = {
      enable = true;
      materializationTimer.enable = true;
    };

    # ── Local AI platform ───────────────────────────────────────────────────
    # Weights/state live on durable /realm; everything binds 127.0.0.1 (reach
    # over Tailscale later). CUDA via per-package overrides — see
    # flake/overlay/package/local-ai.nix and the cuda-maintainers cache below.
    ollama.enable = true; # local LLM/VLM hub
    litellm.enable = true; # Anthropic/OpenAI gateway
    open-webui.enable = true; # chat/RAG/voice frontend
    # llama-server :8081 serving the local reranker (/v1/rerank — an API ollama
    # does not provide). 0.6b Q8, bounded ctx-size (see
    # modules/services/llama-cpp.nix); the 4B Q4 GGUF sits on disk as the
    # quality-tier swap. gpuLayers = 0 is not zero VRAM: the CUDA-linked binary
    # still holds a few hundred MiB of context/compute-buffer even with
    # --n-gpu-layers 0, released on exit. Socket-activated on demand but
    # deliberately outside the gpu-inference admission mesh
    # (modules/services/ai-control.nix), so it coexists with a resident
    # resident GPU inference session instead of making every retrieval turn
    # pay a GPU reload.
    llama-cpp.enable = true;
    kokoro.enable = true; # Kokoro-82M TTS :8880 (CPU, on-demand) — replaces edge-tts
    stt.enable = true; # speech-to-text :8090 — Parakeet TDT, CPU-only, on-demand
  };

  # The sources Sinex reads on this host. Sinnix capture keeps writing its
  # lanes; Sinex reads them beside its own live capture, so the overlap is
  # intended. Historical exports enter through Sinex's staging operations,
  # explicitly, never as activation work.
  services.sinex =
    let
      realm = config.sinnix.paths.realmRoot;
      # Clipboard capture includes both clipboard and primary selections.
      sessionSources = [
        "desktop.hyprland"
        "machine.file-watch"
        "desktop.clipboard"
        "desktop.notifications"
        "media.mpris"
      ];
      sourceCatalog = lib.listToAttrs (
        map (source: {
          name = source.name;
          value = source;
        }) (lib.importJSON "${inputs.sinex}/nix/catalog.json").sources
      );
      sessionDeclarations = map (name: sourceCatalog.${name}) sessionSources;
    in
    {
      nats.producers.${config.services.sinex.session.producer} = {
        writeFamily = "sinex";
        attestedHost = config.services.sinex.host;
        writeSourcePrefixes = sessionSources;
        writeKindPrefixes = lib.unique (lib.concatMap (source: source.eventTypes) sessionDeclarations);
        writeClasses = lib.unique (map (source: source.class) sessionDeclarations);
      };
      exclude = {
        "session.integrations".reason =
          "External integration capture is outside the selected session sources.";
        "session.media".reason = "Screen and microphone capture are outside the selected session sources.";
      };
      session = {
        watch = [
          "${realm}/personal"
          "${realm}/project"
        ];
      };
      discovery = {
        layoutFile = ../../pkgs/sinnix-lib/sinnix_lib/filesystem-layout.json;
        inputRoots = {
          realm = [ realm ];
          projects = [ "${realm}/project" ];
          notes = [ "${realm}/personal" ];
          raw-log = [ "${realm}/personal/journal/raw-log.md" ];
          steering = [ "${realm}/project/steering/repo/steering.sqlite" ];
          library = [ "${realm}/library" ];
          documents = [ "${realm}/document" ];
          downloads = [ "${realm}/inbox/download" ];
        };
        environment.ZSH_HISTFILE = "${realm}/activity/terminal/shell/zsh/history";
      };
    };

  # CUDA builds (ollama-cuda and llama-cpp-cuda) are served
  # by this cache; without it they compile locally. Trusted at switch time.
  nix.settings.substituters = [ "https://cache.nixos-cuda.org" ];
  nix.settings.trusted-public-keys = [
    "cache.nixos-cuda.org:74DUi4Ye579gUqzH4ziL9IyiJBlDpMRn9MBN8oNan9M="
  ];
  # This board's fTPM blocks system activation in systemd-tpm2-setup. Keep
  # TPM2 setup masked on sinnix-prime; Secure Boot key material is file-backed.
  systemd.services.systemd-tpm2-setup.enable = lib.mkForce false;
  systemd.services.systemd-tpm2-setup-early.enable = lib.mkForce false;

  # Long-term journal on the /realm NVMe rather than the wear-limited MX500
  # root, so retention can be generous (100G size cap, 365-day time cap). The
  # source is provisioned before the bind mount by ensure-journal-source.
  # New sources are nested subvolumes, excluding their churn from /realm
  # snapshots. Existing ordinary directories are preserved until explicitly
  # migrated. Sinex's syslog capture is the durable archive; this is the
  # queryable window.
  fileSystems."/var/log/journal" = {
    device = "/realm/state/journal";
    fsType = "none";
    options = [
      "bind"
      "nofail"
    ];
    depends = [ "/realm" ];
  };
  # The persistent journal supplies the OOM/earlyoom kill-event capture.
  # Retention is time-based; the size cap is a backstop, not a preallocation.
  services.journald.settings.Journal = {
    Storage = lib.mkForce "persistent";
    RateLimitIntervalSec = lib.mkForce "30s";
    RateLimitBurst = lib.mkForce 500;
    Compress = lib.mkForce true;
    SyncIntervalSec = lib.mkForce "2min";
    MaxRetentionSec = lib.mkForce "365day";
    SystemMaxUse = lib.mkForce "100G";
    # The journal lives on /realm. At 200G, journald deleted almost every
    # archived file while /realm sat near full, leaving five days of logs.
    SystemKeepFree = lib.mkForce "20G";
    # Sinex's imported ten-file default would rotate this window at about
    # 1 GiB despite the host's 100 GiB budget. Keep count secondary to size
    # and time, including journals split across system and user streams.
    SystemMaxFiles = lib.mkForce 10000;
    SystemMaxFileSize = lib.mkForce "128M";
    MaxFileSec = lib.mkForce "1week";
    ForwardToSyslog = lib.mkForce false;
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
