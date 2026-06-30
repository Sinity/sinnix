{
  mkFeatureModule,
  pkgs,
  lib,
  ...
}@args:
mkFeatureModule {
  path = [
    "desktop"
    "gaming"
  ];
  description = "Gaming support (Steam, gamemode, tools)";
  subFeatures = {
    steam = {
      description = "Steam platform with gamescope session";
      default = true;
    };
    gamemode = {
      description = "Feral gamemode for performance optimization";
      default = true;
    };
    factorio = {
      description = "Authenticated Factorio launcher backed by agenix";
      default = true;
    };
  };
  extraOptions = {
    factorio.username = lib.mkOption {
      type = lib.types.str;
      default = "Sinityy";
      description = "Factorio account username used for authenticated client downloads.";
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
    let
      inherit (config) sinnix;
      capturesRoot = sinnix.paths.capturesRoot;
      replayDir = "${capturesRoot}/replay";

      factorioTokenPath = sinnix.secrets.paths."factorio-token";
      factorioVersion = pkgs.factorio.version;
      factorioSha256 = pkgs.factorio.src.outputHash;
      factorioUrl = pkgs.factorio.src.url;
      factorioLauncher = pkgs.writeShellApplication {
        name = "factorio-steam";
        runtimeInputs = with pkgs; [
          coreutils
          curl
          gnutar
          steam-run
          xz
        ];
        text = ''
          set -euo pipefail

          token_file="${factorioTokenPath}"
          username="${cfg.factorio.username}"
          version="${factorioVersion}"
          archive_name="factorio_alpha_x64-${factorioVersion}.tar.xz"
          cache_root="''${XDG_DATA_HOME:-$HOME/.local/share}/factorio-auth"
          install_root="$cache_root/$version"
          archive_path="$cache_root/$archive_name"
          bin_path="$install_root/x64/factorio"
          refresh=0

          if [[ "''${1-}" == "--refresh" ]]; then
            refresh=1
            shift
          fi

          mkdir -p "$cache_root"

          if [[ ! -r "$token_file" ]]; then
            echo "factorio-steam: missing token at $token_file" >&2
            exit 1
          fi

          if [[ $refresh -eq 1 ]]; then
            rm -rf "$install_root"
            rm -f "$archive_path"
          fi

          if [[ ! -x "$bin_path" ]]; then
            token="$(tr -d '\r\n' < "$token_file")"
            tmp_archive="$(mktemp "$cache_root/factorio.XXXXXX.tar.xz")"
            tmp_dir="$(mktemp -d "$cache_root/factorio.XXXXXX")"

            cleanup() {
              rm -f "$tmp_archive"
              rm -rf "$tmp_dir"
            }
            trap cleanup EXIT

            curl --fail --location --get \
              --data-urlencode "username=$username" \
              --data-urlencode "token=$token" \
              "${factorioUrl}" \
              -o "$tmp_archive"

            printf '%s  %s\n' "${factorioSha256}" "$tmp_archive" | sha256sum --check --status
            tar -xJf "$tmp_archive" -C "$tmp_dir"

            rm -rf "$install_root"
            mv "$tmp_dir" "$install_root"
            mv "$tmp_archive" "$archive_path"
            trap - EXIT
          fi

          exec ${pkgs.steam-run}/bin/steam-run "$bin_path" "$@"
        '';
      };

      # gpu-screen-recorder replay buffer script
      replayBufferScript = pkgs.writeShellApplication {
        name = "replay-buffer";
        runtimeInputs = with pkgs; [
          gpu-screen-recorder
          coreutils
          procps
          libnotify
        ];
        text = ''
          set -euo pipefail
          REPLAY_DIR="${replayDir}"
          DURATION="''${1:-60}"
          PIDFILE="/tmp/replay-buffer.pid"

          if [[ -f "$PIDFILE" ]] && kill -0 "$(cat "$PIDFILE")" 2>/dev/null; then
            # Already running — save current replay
            kill -USR1 "$(cat "$PIDFILE")"
            notify-send -t 3000 "Replay saved" "$REPLAY_DIR"
            exit 0
          fi

          mkdir -p "$REPLAY_DIR"
          gpu-screen-recorder \
            -w screen \
            -f 60 \
            -r "$DURATION" \
            -a default_output \
            -c mp4 \
            -o "$REPLAY_DIR" &
          echo $! > "$PIDFILE"
          notify-send -t 2000 "Replay buffer started" "''${DURATION}s @ 60fps"
        '';
      };

      replayBufferStop = pkgs.writeShellApplication {
        name = "replay-buffer-stop";
        runtimeInputs = with pkgs; [
          coreutils
          procps
          libnotify
        ];
        text = builtins.readFile ./replay-buffer-stop.sh;
      };
    in
    lib.mkMerge [
      # Steam with gamescope
      (lib.mkIf cfg.steam.enable {
        programs.steam = {
          enable = true;
          gamescopeSession.enable = true;
        };

        home-manager.users.${user} = {
          home.packages = with pkgs; [
            mangohud
            steam-run
            protonup-ng
          ];

          home.sessionVariables = {
            # Proton: expose NVAPI so games can use DLSS/DLSS-G/ray tracing
            PROTON_ENABLE_NVAPI = "1";
            DXVK_ENABLE_NVAPI = "1";
            # Proton: don't hide the NVIDIA GPU from DirectX
            PROTON_HIDE_NVIDIA_GPU = "0";
            # VKD3D-proton: enable DX12 ray tracing via Vulkan RT extensions
            VKD3D_CONFIG = "dxr";
            # Shader caches: persist compiled shaders to avoid stutter
            DXVK_STATE_CACHE = "1";
            __GL_SHADER_DISK_CACHE = "1";
            __GL_SHADER_DISK_CACHE_SKIP_CLEANUP = "1";
            # HDR passthrough for Proton (games that support HDR natively)
            DXVK_HDR = "1";
            # MangoHud: inject into all Vulkan/OpenGL apps globally
            # Starts hidden (no_display in config), toggle with Shift_R+F12
            MANGOHUD = "1";
          };

          # MangoHud overlay configuration
          xdg.configFile."MangoHud/MangoHud.conf".text = ''
            # Position & appearance
            position=top-left
            font_size=20
            background_alpha=0.3
            round_corners=8

            # Metrics
            fps
            frametime=0
            frame_timing
            gpu_stats
            gpu_temp
            gpu_power
            gpu_mem_clock
            gpu_core_clock
            vram
            cpu_stats
            cpu_temp
            cpu_power
            ram

            # Behavior
            toggle_hud=Shift_R+F12
            toggle_fps_limit=Shift_R+F11
            fps_limit=0,60,120
            no_display
          '';

          # Persistence for Proton GE versions
          # (Steam library itself is already persisted)
        };

        # Persist shader caches and Proton GE across reboots
        sinnix.persistence.home.directories = [
          ".local/share/vulkan" # Vulkan pipeline caches
          ".local/share/Steam/compatibilitytools.d" # Proton GE installs
        ];
      })

      # Gamemode: CPU governor + scheduler tuning for gaming sessions
      (lib.mkIf cfg.gamemode.enable {
        programs.gamemode = {
          enable = true;
          settings = {
            general = {
              renice = 10;
              softrealtime = "auto";
              inhibit_screensaver = 1;
            };
            gpu = {
              apply_gpu_optimisations = "accept-responsibility";
              gpu_device = 0;
            };
            custom = {
              start = "${pkgs.libnotify}/bin/notify-send -t 2000 'GameMode' 'Performance mode active'";
              end = "${pkgs.libnotify}/bin/notify-send -t 2000 'GameMode' 'Performance mode off'";
            };
          };
        };
      })

      # Replay buffer tooling
      (lib.mkIf cfg.steam.enable {
        home-manager.users.${user}.home.packages = [
          replayBufferScript
          replayBufferStop
        ];
      })

      # Factorio launcher using the agenix-managed token at runtime
      (lib.mkIf cfg.factorio.enable {
        home-manager.users.${user}.home.packages = [ factorioLauncher ];
      })
    ];
} args
