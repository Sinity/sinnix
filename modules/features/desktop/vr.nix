# VR streaming to standalone headsets (Meta Quest 3)
#
# ═══════════════════════════════════════════════════════════════════════════════
# ARCHITECTURE
# ═══════════════════════════════════════════════════════════════════════════════
#
# Two streaming stacks are available (enable one):
#
#   WiVRn + Monado (default):
#     Game → OpenComposite (OpenVR→OpenXR translation) → Monado (OpenXR runtime) → WiVRn (encode+stream) → Quest
#     - No SteamVR dependency — Monado replaces it entirely
#     - OpenComposite translates legacy SteamVR/OpenVR games to OpenXR
#     - Native OpenXR games talk to Monado directly (no translation)
#     - Lower latency potential (Monado compositor is lighter than SteamVR's)
#
#   ALVR (alternative):
#     Game → SteamVR Runtime → ALVR (encode+stream) → Quest
#     - Requires SteamVR (proprietary, poorly maintained on Linux)
#     - More mature project, larger community, more troubleshooting resources
#     - Single monolithic app handles everything
#
# Both use NVENC hardware video encoding on NVIDIA GPUs.
#
# ═══════════════════════════════════════════════════════════════════════════════
# QUEST 3 INITIAL SETUP
# ═══════════════════════════════════════════════════════════════════════════════
#
# 1. Enable developer mode:
#    - Install Meta Horizon app on phone
#    - Go to Devices → select Quest 3 → Developer Mode → enable
#    - This requires a Meta developer account (free, just register)
#
# 2. Connect Quest to PC via USB-C:
#    - Needs a USB 3.0+ cable (the included charging cable is USB 2.0, too slow)
#    - A 3-5m braided "Link cable" is ~€15-25 and gives room to move
#    - Accept "Allow USB debugging" prompt on the headset when it appears
#    - Verify: `adb devices` should show your Quest
#
# 3. Sideload the streaming client:
#    For WiVRn:
#      - Download wivrn-client APK from WiVRn GitHub releases
#      - `adb install wivrn-client.apk`
#    For ALVR:
#      - Download alvr_client_quest_3.apk from ALVR GitHub releases
#      - `adb install alvr_client_quest_3.apk`
#
# 4. Connect and stream:
#    For WiVRn:
#      - PC: run `wivrn-server`
#      - Quest: launch WiVRn app → discovers PC via Avahi → connect
#    For ALVR:
#      - PC: run `alvr_dashboard` (web UI at localhost:8082)
#      - Quest: launch ALVR app → discovers PC on network → pair
#    - Launch any SteamVR or OpenXR game on PC → renders in headset
#
# ═══════════════════════════════════════════════════════════════════════════════
# USB vs WIRELESS STREAMING
# ═══════════════════════════════════════════════════════════════════════════════
#
# USB (recommended with current Wi-Fi 5 router):
#   - Latency: ~5ms (vs ~30-50ms wireless)
#   - Bandwidth: 2-3 Gbps over USB 3.2
#   - Bitrate: 200-500 Mbps (vs 100-150 Mbps wireless)
#   - Quest appears as virtual Ethernet device at 172.x.x.x
#   - No firewall ports needed — traffic stays on the cable
#   - Both WiVRn and ALVR auto-detect USB connection
#
# Wireless (limited by Netgear R6220 / Wi-Fi 5):
#   - Current router: 802.11ac, VHT80, MT76x2 — max ~400 Mbps real-world
#   - Quest 3 has Wi-Fi 6E radio (massively underutilized by this router)
#   - Upgrading to a dedicated Wi-Fi 6E AP would unlock full wireless potential
#   - Quest should be on 5 GHz band, PC wired via Ethernet
#
# ═══════════════════════════════════════════════════════════════════════════════
# ENVIRONMENT VARIABLES
# ═══════════════════════════════════════════════════════════════════════════════
#
# Set automatically in user session when wivrn sub-feature is enabled:
#
#   XR_RUNTIME_JSON  → Points OpenXR loader at Monado's runtime manifest.
#                      Contains absolute Nix store paths to libopenxr_monado.so.
#
#   OXR_LIBPATH      → Points Steam's pressure-vessel at OpenComposite's
#                      vrclient.so. When a SteamVR game loads, it finds
#                      OpenComposite here → translates OpenVR calls → Monado.
#                      Native OpenXR games skip this entirely.
#
# ═══════════════════════════════════════════════════════════════════════════════
# QUEST MANAGEMENT FROM PC
# ═══════════════════════════════════════════════════════════════════════════════
#
# Tools provided by quest-tools sub-feature:
#
#   adb          Core device communication (sideloading, file transfer, shell)
#   sidequest    GUI sideloader + app store + device tuning dashboard
#   scrcpy       Mirror Quest display to PC window in real-time
#
# ── Sideloading ──────────────────────────────────────────────────────────────
#
#   adb install app.apk               Install APK
#   adb install -r updated.apk        Update existing app
#   adb shell pm list packages -3     List sideloaded (third-party) apps
#   adb shell pm uninstall com.x.y    Remove app
#
# ── File transfer ────────────────────────────────────────────────────────────
#
#   adb push movie.mp4 /sdcard/Movies/          Upload file to Quest
#   adb pull /sdcard/Oculus/Screenshots/ ./     Download from Quest
#   adb shell ls /sdcard/Android/data/          List app data dirs
#
# ── Wireless ADB (after initial USB connection) ─────────────────────────────
#
#   adb tcpip 5555                       Enable wireless ADB on Quest
#   adb connect 192.168.1.XXX:5555       Connect wirelessly (same network)
#   # Then unplug USB — all adb commands now work over Wi-Fi
#
# ── Screen mirroring ─────────────────────────────────────────────────────────
#
#   scrcpy                               Mirror Quest to PC window
#   scrcpy --crop 1920:1080:0:0          Cropped view
#   scrcpy --record session.mp4          Mirror + record to file
#   # Note: mirrors 2D home/app UI, not the stereoscopic VR compositor
#
# ── Performance tuning via ADB ───────────────────────────────────────────────
#
#   # Refresh rate (72, 80, 90, 120 Hz)
#   adb shell setprop debug.oculus.refreshRate 120
#
#   # Render resolution (default ~1680, Quest 3 native: 2064x2208 per eye)
#   adb shell setprop debug.oculus.textureWidth 2064
#   adb shell setprop debug.oculus.textureHeight 2208
#
#   # GPU/CPU performance level (0=low, 4=max — more power/heat)
#   adb shell setprop debug.oculus.gpuLevel 4
#   adb shell setprop debug.oculus.cpuLevel 4
#
#   # Fixed Foveated Rendering (0=off, 1-4=aggressive — saves GPU at edge blur cost)
#   adb shell setprop debug.oculus.foveation.level 0
#   adb shell setprop debug.oculus.foveation.dynamic 1    # or dynamic mode
#
#   # Disable guardian boundary (seated/stationary use)
#   adb shell setprop debug.oculus.guardian_pause 1
#
#   # Disable chromatic aberration correction (slight perf gain)
#   adb shell setprop debug.oculus.forceChroma 0
#
#   # Video capture quality
#   adb shell setprop debug.oculus.capture.width 1920
#   adb shell setprop debug.oculus.capture.height 1080
#   adb shell setprop debug.oculus.capture.bitrate 10000000  # 10 Mbps
#
#   # Device info
#   adb shell getprop ro.build.display.id       # firmware version
#   adb shell dumpsys battery                     # battery/temp/status
#   adb shell df -h /sdcard                       # storage usage
#
#   Note: setprop values reset on Quest reboot. SideQuest persists some.
#
# ── Additional device management via ADB ────────────────────────────────────
#
#   # Performance overlay (FPS, GPU/CPU usage, thermals)
#   adb shell setprop debug.oculus.showPerfHud 1    # 0=off, 1-4 detail levels
#
#   # Wi-Fi management (avoid painful VR keyboard)
#   adb shell cmd wifi connect-network "SSID" wpa2 "password"
#   adb shell cmd wifi list-networks
#   adb shell cmd wifi forget-network <networkId>
#
#   # Text input (type from PC keyboard into Quest fields)
#   adb shell input text "hello@email.com"
#
#   # Button simulation
#   adb shell input keyevent KEYCODE_BACK
#   adb shell input keyevent KEYCODE_HOME
#   adb shell input keyevent KEYCODE_WAKEUP
#
#   # App control
#   adb shell am force-stop com.package.name         # kill misbehaving app
#   adb shell pm clear com.package.name              # reset app data
#   adb shell am start -n com.pkg/.MainActivity      # launch app directly
#
#   # System diagnostics
#   adb shell dumpsys thermalservice                  # thermal state
#   adb shell dumpsys meminfo                         # memory usage
#   adb shell dumpsys activity activities | grep mResumedActivity  # foreground app
#   adb logcat -d | tail -100                         # system log (debug sideloads)
#
#   # Volume (0-15, stream 3 = media)
#   adb shell media volume --set 10 --stream 3
#
#   # Sleep timeout (milliseconds, 0 = never while worn)
#   adb shell settings put system screen_off_timeout 300000
#
#   Not possible via ADB: Meta account changes, IPD adjustment (physical slider),
#   Bluetooth controller pairing, hand tracking toggle, Meta Store access.
#
# ═══════════════════════════════════════════════════════════════════════════════
# DEBLOATING
# ═══════════════════════════════════════════════════════════════════════════════
#
# Quest 3 ships with Meta bloatware that runs in the background, consuming
# battery, CPU cycles, and sending telemetry. ADB can disable (not uninstall)
# system packages without root.
#
# ── Commands ────────────────────────────────────────────────────────────────
#
#   # List all Meta/Oculus system packages
#   adb shell pm list packages -s | grep -E "oculus|meta|facebook"
#
#   # Disable a package (stops it, hides it, fully reversible)
#   adb shell pm disable-user --user 0 com.package.name
#
#   # Re-enable if something breaks
#   adb shell pm enable com.package.name
#
#   # List currently disabled packages
#   adb shell pm list packages -d
#
#   # More aggressive removal (still reversible via factory reset)
#   adb shell pm uninstall -k --user 0 com.package.name
#
# ── Safe to disable ────────────────────────────────────────────────────────
#
#   com.facebook.arvr.quillplayer         Quill animation player
#   com.oculus.socialplatform             Meta social/people features
#   com.oculus.helpcenter                 Help center
#   com.meta.curiouscast                  Meta casting service
#   com.oculus.firsttimenux               First-time setup wizard (after setup)
#   com.oculus.metacam                    Meta Camera app
#   com.oculus.mobileintent               Phone notification bridge
#   com.facebook.messengerxr              Messenger VR
#   com.oculus.gamingactivity             Gaming activity feed
#   com.oculus.explore                    Explore tab / Meta recommendations
#   com.oculus.assistant                  Meta voice assistant
#
# ── NEVER disable (will brick the UI) ──────────────────────────────────────
#
#   com.oculus.panelapp.settings          Settings UI
#   com.oculus.guardian                   Safety boundary system
#   com.oculus.vrshell                    Home shell / system UI
#   com.oculus.xrstreamingclient          Streaming infrastructure (Link/AirLink)
#   com.oculus.systemux                   Core system UX
#
# ── Telemetry reduction ────────────────────────────────────────────────────
#
# Without root, on-device telemetry can't be fully blocked. However:
#   - Router-level DNS blocking (adblock-fast with Hagezi Pro on R6220)
#     already blocks many Meta/Facebook tracking domains for all LAN devices
#   - Disabling social/messenger/explore packages reduces telemetry surface
#   - SideQuest's device settings page can disable some telemetry toggles
#
# ── Community debloat resources ────────────────────────────────────────────
#
# The Community wikis maintain up-to-date safe-to-disable
# package list. SideQuest also has a built-in package manager GUI that
# shows system apps with disable/enable toggles. No single canonical
# debloat tool exists for Quest (unlike Android's Universal Debloater).
# Always check community lists before disabling unfamiliar packages —
# Meta changes package names across firmware versions.
#
# ═══════════════════════════════════════════════════════════════════════════════
# VR VIDEO PLAYBACK
# ═══════════════════════════════════════════════════════════════════════════════
#
# VR videos (SBS, 180°, 360°) play natively on Quest — no PC streaming needed.
# The Quest's Snapdragon XR2 Gen 2 hardware-decodes up to 8K h.265 locally.
# Streaming through ALVR/WiVRn would add pointless double-encoding.
#
# Formats:
#   SBS (Side-by-Side)   Left/right eye packed horizontally — 3D content
#   180° SBS             SBS + hemisphere projection — immersive forward-facing
#   360° SBS             SBS + full sphere — look-anywhere immersive
#   360° Mono            Single-eye full sphere — travel/360 camera footage
#
# Players (install on Quest):
#   Skybox VR            Best format support, streams from PC via SMB/DLNA
#   DeoVR                Popular free player, similar capabilities
#   Meta built-in        Basic player, handles SBS/180/360
#
# Getting video onto Quest:
#   adb push movie.mp4 /sdcard/Movies/      Copy via USB (fast, ~300 MB/s)
#   Skybox network browse                    Stream from PC SMB share (no copy)
#
# Resolution tip: 4K SBS minimum for sharp image. 5.7K-8K for best immersion.
# 1080p SBS looks noticeably blurry at Quest 3's 2064x2208 per-eye resolution.
#
# ═══════════════════════════════════════════════════════════════════════════════
# APK SOURCES & SIDELOAD ECOSYSTEM
# ═══════════════════════════════════════════════════════════════════════════════
#
#   SideQuest          Curated sideload store with ratings, desktop app + web
#   Quest App Lab      Meta's official early-access channel (direct link install)
#   GitHub releases    Open-source VR apps (ALVR, WiVRn, QuestCraft, etc.)
#   itch.io            Indie VR games with Quest builds
#
# Notable sideload apps:
#   QuestCraft         Minecraft Java Edition in VR (PojavLauncher + Vivecraft)
#   Lambda1VR          Half-Life 1 native Quest port
#   QuestZDoom         Doom/Doom2/Heretic in VR
#   Dr. Beef ports     Quake 1/2/3, RTCW, Jedi Knight II — native Quest ports
#   Virtual Desktop    Commercial PC streaming + virtual multi-monitor (~€20)
#
# ═══════════════════════════════════════════════════════════════════════════════
# COMMUNITY & RESOURCES
# ═══════════════════════════════════════════════════════════════════════════════
#
#   r/virtualreality_linux    Linux VR — ALVR, WiVRn, Monado issues
#   r/sidequest               SideQuest app store community
#   r/OculusQuest             General Quest community (large)
#   WiVRn GitHub              Issues, releases, documentation
#   Monado GitLab             freedesktop.org hosted, wiki + issues
#   OpenComposite GitLab      Game compatibility, translation layer issues
#   SideQuest Discord         Real-time sideloading help
#
# ═══════════════════════════════════════════════════════════════════════════════
# ROOTING (not recommended)
# ═══════════════════════════════════════════════════════════════════════════════
#
# No public root exploit for Quest 3. Developer mode covers ~95% of use cases
# (sideloading, ADB shell, file transfer, setprop tuning, wireless ADB).
# Root would give: custom firmware, telemetry removal, kernel mods, full fs.
# Risks: Meta can brick online functionality, warranty void, no alt OS exists.
#
{
  mkFeatureModule,
  lib,
  pkgs,
  ...
}@args:
mkFeatureModule {
  path = [
    "desktop"
    "vr"
  ];
  description = "VR streaming to standalone headsets (Quest 3)";
  subFeatures = {
    wivrn = {
      description = "WiVRn + Monado OpenXR streaming stack";
      default = true;
    };
    alvr = {
      description = "ALVR wireless VR streaming server (alternative to WiVRn)";
      default = false;
    };
    quest-tools = {
      description = "ADB, SideQuest, scrcpy, and udev rules for Meta Quest management";
      default = true;
    };
  };
  configFn =
    {
      config,
      lib,
      pkgs,
      cfg,
      user,
      ...
    }:
    lib.mkMerge [

      # ── WiVRn + Monado + OpenComposite ────────────────────────────────────────
      (lib.mkIf cfg.wivrn.enable {
        home-manager.users.${user} = {
          home.packages = with pkgs; [
            wivrn
            monado
            opencomposite
          ];

          # Point the OpenXR loader at Monado, and OpenVR games at OpenComposite
          home.sessionVariables = {
            # Monado as the system OpenXR runtime
            XR_RUNTIME_JSON = "${pkgs.monado}/share/openxr/1/openxr_monado.json";
            # OpenComposite intercepts SteamVR/OpenVR → forwards to Monado
            # Pressure-vessel / Steam looks for vrclient.so at this path
            OXR_LIBPATH = "${pkgs.opencomposite}/lib/opencomposite/bin/linux64/vrclient.so";
          };
        };

        # WiVRn uses Avahi for headset discovery on the local network
        services.avahi = {
          enable = true;
          publish.enable = true;
          publish.userServices = true;
        };

        # WiVRn streaming port
        networking.firewall = {
          allowedTCPPorts = [ 9757 ];
          allowedUDPPorts = [ 9757 ];
        };
      })

      # ── ALVR ──────────────────────────────────────────────────────────────────
      (lib.mkIf cfg.alvr.enable {
        home-manager.users.${user}.home.packages = [ pkgs.alvr ];

        # ALVR streaming ports: 9943 (handshake/control), 9944 (video/audio)
        networking.firewall = {
          allowedTCPPorts = [
            9943
            9944
          ];
          allowedUDPPorts = [
            9943
            9944
          ];
        };
      })

      # ── Quest tools: ADB, SideQuest, scrcpy ─────────────────────────────────
      (lib.mkIf cfg.quest-tools.enable {
        # Meta/Oculus USB vendor ID for udev
        services.udev.extraRules = ''
          # Meta Quest headsets (vendor 2833)
          SUBSYSTEM=="usb", ATTR{idVendor}=="2833", MODE="0666", GROUP="adbusers"
        '';

        users.groups.adbusers = { };
        users.users.${user}.extraGroups = lib.mkAfter [ "adbusers" ];

        environment.systemPackages = with pkgs; [
          # Core ADB for sideloading, device config, file transfer
          android-tools

          # SideQuest: GUI sideloader, app store, device tuning dashboard
          # Wraps ADB with one-click resolution/refresh rate/FFR presets
          sidequest

          # scrcpy: mirror Quest display to PC window in real-time
          # Useful for spectating, recording, debugging sideloaded apps
          scrcpy
        ];
      })
    ];
} args
