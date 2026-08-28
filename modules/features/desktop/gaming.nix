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
      steamLibraryRoot = "${sinnix.paths.mediaRoot}/Steam";
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
    in
    lib.mkMerge [
      (lib.mkIf cfg.steam.enable {
        programs.steam = {
          enable = true;
          gamescopeSession.enable = true;
        };

        # Steam keeps its XDG data path, while the install and library live on
        # the canonical re-acquirable media volume.
        systemd.tmpfiles.rules = [
          "d ${steamLibraryRoot} 0750 ${user} users -"
          "L+ /home/${user}/.local/share/Steam - - - - ${steamLibraryRoot}"
        ];

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
        };

        # Persist shader caches across reboots. Steam itself is rooted at
        # steamLibraryRoot, so its compatibility tools are persisted with it.
        sinnix.persistence.home.directories = [ ".local/share/vulkan" ];
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

      # Factorio launcher using the agenix-managed token at runtime
      (lib.mkIf cfg.factorio.enable {
        home-manager.users.${user}.home.packages = [ factorioLauncher ];
      })
    ];
} args
