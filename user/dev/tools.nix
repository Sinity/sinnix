{
  pkgs,
  lib,
  inputs,
  dotsPath,
  secretPaths,
  config,
  sinnix,
  ...
}:
let
  homeDir = config.home.homeDirectory;
  realmRoot = sinnix.paths.realmRoot;
  mcpPython = pkgs.python3.withPackages (ps: [ ps.fastmcp ps.qdrant-client ps.psycopg ]);
  mcpQdrantBin = pkgs.writeShellScriptBin "mcp-qdrant" ''
    exec ${mcpPython}/bin/python3 ${inputs.self}/scripts/mcp-qdrant.py "$@"
  '';
  mcpPostgresBin = pkgs.writeShellScriptBin "mcp-postgres" ''
    exec ${mcpPython}/bin/python3 ${inputs.self}/scripts/mcp-postgres.py "$@"
  '';
  mkDotsRepoLink = rel: dotsPath + "/" + rel;
  codexProjectPaths = [
    "${realmRoot}/project/sinnix"
    "${realmRoot}/project/sinex"
    "${realmRoot}/data/finance/jpk/finale"
    "${realmRoot}/project/voyage-embeddings"
    homeDir
    "${homeDir}/.local/share/weechat/logs"
    "${realmRoot}/knowledgebase"
    "${homeDir}/.codex/sessions"
    "${realmRoot}/sinnix"
    "${homeDir}/session-snapshots/20251013T000834"
    "${realmRoot}/project/knowledge-extract"
  ];
  codexProjects = builtins.listToAttrs (map (path: {
    name = path;
    value = { trust_level = "trusted"; };
  }) codexProjectPaths);
  codexConfig = {
    model = "gpt-5-codex";
    model_reasoning_effort = "high";
    projects = codexProjects;
    mcp_servers = {
      github = {
        url = "https://api.githubcopilot.com/mcp/";
        bearer_token_env_var = "GITHUB_TOKEN";
      };
      "postgres-local" = {
        command = "${homeDir}/.local/bin/mcp-postgres";
        args = [ ];
      };
      playwright = {
        command = "npx";
        args = [ "@playwright/mcp@latest" ];
      };
      context7 = {
        command = "npx";
        args = [ "-y" "@upstash/context7-mcp@latest" ];
      };
      firecrawl = {
        command = "npx";
        args = [ "-y" "firecrawl-mcp@latest" ];
        env = {
          FIRECRAWL_API_KEY = "$FIRECRAWL_API_KEY";
        };
      };
      qdrant = {
        command = "${homeDir}/.local/bin/mcp-qdrant";
        args = [ ];
        env = {
          QDRANT_URL = "http://127.0.0.1:6333";
        };
      };
    };
    features.rmcp_client = true;
  };
  codexToml = pkgs.formats.toml { };
  codexConfigFile = codexToml.generate "codex-config.toml" codexConfig;
in
{
  # Developer-focused toolchain packages kept in the user's profile to reduce
  # system-wide rebuild churn while preserving the previous package set.
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
        perf
        phoronix-test-suite
        pikchr
        pipes
        plantuml
        ploticus
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
        uv
        visidata
        zed-editor
        vulkan-tools
        vulkan-validation-layers
        wayland-utils
        xan
        zk
      ] ++ [
        mcpQdrantBin
        mcpPostgresBin
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

      restoreGcloud = lib.hm.dag.entryAfter [ "writeBoundary" ] ''
        if [ -f ${secretPaths."gcloud-config.tar.gz"} ]; then
          mkdir -p "$HOME/.config"
          rm -rf "$HOME/.config/gcloud"
          if ! ${pkgs.gzip}/bin/gzip -dc ${
            secretPaths."gcloud-config.tar.gz"
          } | ${pkgs.gnutar}/bin/tar -xC "$HOME/.config"; then
            echo "warning: unable to restore gcloud config archive" >&2
          fi
        fi
      '';

    };
  };

  xdg.configFile = {
    "opencode/opencode.json".text =
      lib.replaceStrings
        [ "/home/sinity" ]
        [ homeDir ]
        (builtins.readFile (dotsPath + "/opencode/opencode.json"));

    "sqlitebrowser/sqlitebrowser.conf".text =
      lib.replaceStrings
        [ "/home/sinity" ]
        [ homeDir ]
        (builtins.readFile (dotsPath + "/sqlitebrowser/sqlitebrowser.conf"));

    "ripgrep-all/config.jsonc".source = dotsPath + "/ripgrep-all/config.jsonc";

    "marimo/marimo.toml".source = dotsPath + "/marimo/marimo.toml";
  };

  home.file = {
    ".codex/config.toml".source = codexConfigFile;
    ".local/bin/mcp-qdrant".source = "${mcpQdrantBin}/bin/mcp-qdrant";
    ".local/bin/mcp-postgres".source = "${mcpPostgresBin}/bin/mcp-postgres";
    ".gemini/settings.json".source = mkDotsRepoLink "gemini/settings.json";
  };
}
