{
  pkgs,
  lib,
  dotsPath,
  secretPaths,
  ...
}:
{
  # Developer-focused toolchain packages kept in the user's profile to reduce
  # system-wide rebuild churn while preserving the previous package set.
  home.packages = lib.mkAfter (
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
      glxinfo
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
      vulkan-tools
      vulkan-validation-layers
      wayland-utils
      xan
      zk
    ]
  );

  xdg.configFile."sqlitebrowser/sqlitebrowser.conf".source =
    dotsPath + "/sqlitebrowser/sqlitebrowser.conf";

  xdg.configFile."ripgrep-all/config.jsonc".source = dotsPath + "/ripgrep-all/config.jsonc";

  xdg.configFile."sinex" = {
    source = dotsPath + "/sinex";
    recursive = true;
  };

  home.activation.restoreConfigstore = lib.hm.dag.entryAfter [ "writeBoundary" ] ''
    if [ -f ${secretPaths."configstore-update-notifier"} ]; then
      mkdir -p "$HOME/.config/configstore"
      rm -rf "$HOME/.config/configstore/update-notifier-@google"
      ${pkgs.gzip}/bin/gzip -dc ${
        secretPaths."configstore-update-notifier"
      } | ${pkgs.gnutar}/bin/tar -xC "$HOME/.config/configstore"
    fi
  '';

  home.activation.restoreGcloud = lib.hm.dag.entryAfter [ "writeBoundary" ] ''
    if [ -f ${secretPaths."gcloud-config.tar.gz"} ]; then
      mkdir -p "$HOME/.config"
      rm -rf "$HOME/.config/gcloud"
      ${pkgs.gzip}/bin/gzip -dc ${
        secretPaths."gcloud-config.tar.gz"
      } | ${pkgs.gnutar}/bin/tar -xC "$HOME/.config"
    fi
  '';
}
