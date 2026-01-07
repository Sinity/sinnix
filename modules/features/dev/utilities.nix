{
  pkgs,
  lib,
  config,
  ...
}:
let
  cfg = config.sinnix.features.dev.utilities;
  user = config.sinnix.user.name;
in
{
  options.sinnix.features.dev.utilities = {
    enable = lib.mkEnableOption "General Development Utilities";
  };

  config = lib.mkIf cfg.enable {
    home-manager.users.${user} = { pkgs, lib, inputs, config, dotsRepoPath, secretPaths, sinnix, ... }: 
      let
        repoRoot = sinnix.paths.projectRoot;
        devenvPkg = inputs.devenv.packages.${pkgs.stdenv.hostPlatform.system}.devenv;
        mcpPython = pkgs.python3.withPackages (ps: [
          ps.fastmcp
          ps.qdrant-client
          ps.psycopg
        ]);
        mcpQdrantBin = pkgs.writeShellScriptBin "mcp-qdrant" ''
          exec ${mcpPython}/bin/python3 ${repoRoot}/scripts/mcp-qdrant.py "$@"
        '';
        mcpPostgresBin = pkgs.writeShellScriptBin "mcp-postgres" ''
          exec ${mcpPython}/bin/python3 ${repoRoot}/scripts/mcp-postgres.py "$@"
        '';
        mcpSqliteBin = pkgs.writeShellScriptBin "mcp-sqlite" ''
          exec ${mcpPython}/bin/python3 ${repoRoot}/scripts/mcp-sqlite.py "$@"
        '';
        mcpContext7Bin = pkgs.writeShellScriptBin "mcp-context7" ''
          set -euo pipefail

          if [ -z "''${CONTEXT7_API_KEY:-}" ]; then
            echo "CONTEXT7_API_KEY is not set" >&2
            exit 1
          fi

          exec npx -y @upstash/context7-mcp@latest --api-key "$CONTEXT7_API_KEY"
        '';
        mcpFirecrawlBin = pkgs.writeShellScriptBin "mcp-firecrawl" ''
          set -euo pipefail

          api_key="''${FIRECRAWL_API_KEY:-}"
          if [ -z "$api_key" ] && [ -r /run/agenix/firecrawl-api-key ]; then
            api_key="$(< /run/agenix/firecrawl-api-key)"
          fi

          if [ -z "$api_key" ]; then
            echo "FIRECRAWL_API_KEY not set and /run/agenix/firecrawl-api-key missing" >&2
            exit 1
          fi

          exec env FIRECRAWL_API_KEY="$api_key" npx -y firecrawl-mcp@latest
        '';
        mcpPlaywrightBin = pkgs.writeShellScriptBin "mcp-playwright" ''
          set -euo pipefail
          exec npx -y @playwright/mcp@latest
        '';
        mkDotsRepoLink = rel: config.lib.file.mkOutOfStoreSymlink (dotsRepoPath + "/" + rel);
      in
      {
        home = {
          packages = lib.mkAfter (
            with pkgs;
            [
              breakpad
              cargo-bloat
              cargo-deny
              cargo-depgraph
              cargo-expand
              cargo-flamegraph
              cargo-llvm-lines
              cargo-machete
              cargo-outdated
              cargo-udeps
              cbonsai
              cmake
              cocogitto
              d2
              drm_info
              dua
              duckdb
              flent
              fselect
              gcc
              gdb
              git-annex
              git-cliff
              git-filter-repo
              gitstats
              glmark2
              gnumake
              gnuplot
              google-cloud-sdk
              gource
              hyperfine
              intel-gpu-tools
              libva-utils
              linuxPackages.cpupower
              linuxPackages.turbostat
              lm_sensors
              man-pages
              man-pages-posix
              mesa-demos
              meson
              miller
              ncdu
              netperf
              ninja
              nitch
              nix-doc
              nix-fast-build
              nix-health
              nix-index
              nix-prefetch-git
              nix-tree
              devenvPkg
              perf
              phoronix-test-suite
              pikchr
              pipes
              plantuml
              # ploticus  # Broken build, temporarily disabled
              powertop
              python312Packages.speedtest-cli
              rt-tests
              s-tui
              scc
              stress-ng
              stressapptest
              structurizr-cli
              sysbench
              sysstat
              toipe
              tty-clock
              ttyper
              polylogue
              uv
              # visidata # Broken due to arrow-cpp build failure
              yt-dlp
              gallery-dl
              zed-editor
              vulkan-tools
              vulkan-validation-layers
              wayland-utils
              xan
              zk
            ]
            ++ [
              mcpQdrantBin
              mcpPostgresBin
              mcpSqliteBin
              mcpContext7Bin
              mcpFirecrawlBin
              mcpPlaywrightBin
            ]
          );

          activation = {
            restoreConfigstore = lib.hm.dag.entryAfter [ "writeBoundary" ] ''
              if [ -f ${secretPaths."configstore-update-notifier"} ]; then
                mkdir -p "$HOME/.config/configstore"
                rm -rf "$HOME/.config/configstore/update-notifier-@google"
                if ! ${pkgs.gzip}/bin/gzip -dc ${
                  secretPaths."configstore-update-notifier"
                } | ${pkgs.gnutar}/bin/tar -xC "$HOME/.config/configstore"; then
                  echo "warning: unable to restore configstore notifier archive" >&2
                fi
              fi
            '';
            prepareCodexSkills = lib.hm.dag.entryBefore [ "linkGeneration" ] ''
              if [ -e "$HOME/.codex/skills" ] && [ ! -L "$HOME/.codex/skills" ]; then
                rm -rf "$HOME/.codex/skills"
              fi
            '';
          };
        };

        xdg.configFile = {
          "ai" = {
            source = mkDotsRepoLink "ai";
            recursive = true;
          };
          "opencode/opencode.json".source = mkDotsRepoLink "opencode/opencode.json";

          "sqlitebrowser/sqlitebrowser.conf".source = mkDotsRepoLink "sqlitebrowser/sqlitebrowser.conf";

          "ripgrep-all/config.jsonc".source = mkDotsRepoLink "ripgrep-all/config.jsonc";

          "marimo/marimo.toml".source = mkDotsRepoLink "marimo/marimo.toml";
        };

        home.file = {
          ".codex/config.toml" = {
            source = mkDotsRepoLink "codex/config.toml";
            force = true;
          };
          ".codex/skills" = {
            source = mkDotsRepoLink "codex/skills";
            force = true;
            recursive = true;
          };
          ".local/bin/ai".source =
            config.lib.file.mkOutOfStoreSymlink (repoRoot + "/scripts/ai");
          ".local/bin/mcp-qdrant".source = "${mcpQdrantBin}/bin/mcp-qdrant";
          ".local/bin/mcp-postgres".source = "${mcpPostgresBin}/bin/mcp-postgres";
          ".local/bin/mcp-sqlite".source = "${mcpSqliteBin}/bin/mcp-sqlite";
          ".local/bin/mcp-context7".source = "${mcpContext7Bin}/bin/mcp-context7";
          ".local/bin/mcp-firecrawl".source = "${mcpFirecrawlBin}/bin/mcp-firecrawl";
          ".local/bin/mcp-playwright".source = "${mcpPlaywrightBin}/bin/mcp-playwright";
          ".gemini/settings.json" = {
            source = mkDotsRepoLink "gemini/settings.json";
            force = true;
          };
        };
      };
  };
}
