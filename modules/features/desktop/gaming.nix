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
      factorioTokenPath = config.sinnix.secrets.paths."factorio-token";
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
      # Steam with gamescope
      (lib.mkIf cfg.steam.enable {
        programs.steam = {
          enable = true;
          gamescopeSession.enable = true;
        };

        home-manager.users.${user}.home.packages = with pkgs; [
          mangohud
          steam-run
        ];
      })

      # Gamemode for performance
      (lib.mkIf cfg.gamemode.enable {
        programs.gamemode.enable = true;
      })

      # Factorio launcher using the agenix-managed token at runtime
      (lib.mkIf cfg.factorio.enable {
        home-manager.users.${user}.home.packages = [ factorioLauncher ];
      })
    ];
} args
