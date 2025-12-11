{
  pkgs,
  lib,
  inputs,
  dotsRepoPath,
  secretPaths,
  config,
  sinnix,
  ...
}:
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
  mkDotsRepoLink = rel: config.lib.file.mkOutOfStoreSymlink (dotsRepoPath + "/" + rel);
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
        devenvPkg
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
      ]
      ++ [
        mcpQdrantBin
        mcpPostgresBin
        mcpSqliteBin
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
    };
  };

  xdg.configFile = {
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
    ".local/bin/mcp-qdrant".source = "${mcpQdrantBin}/bin/mcp-qdrant";
    ".local/bin/mcp-postgres".source = "${mcpPostgresBin}/bin/mcp-postgres";
    ".local/bin/mcp-sqlite".source = "${mcpSqliteBin}/bin/mcp-sqlite";
    ".gemini/settings.json" = {
      source = mkDotsRepoLink "gemini/settings.json";
      force = true;
    };
  };
}
