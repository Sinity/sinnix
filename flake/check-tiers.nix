{ lib }:
let
  coverage = import ./test-coverage.nix;
  smokeName = subject: "smoke-" + lib.replaceStrings [ "." ] [ "-" ] subject;

  semanticFeatureSubjects = [
    "cli.polylogue"
    "desktop.audio"
    "desktop.browser"
    "desktop.common-apps"
    "desktop.gaming"
    "desktop.hyprland"
    "desktop.mime"
    "desktop.terminal"
    "dev.editors"
    "dev.git"
    "dev.mcp-servers"
    "dev.shell"
  ];

  semanticServiceSubjects = [
    "below"
    "polylogue"
    "power-watchdog"
    "sentinel"
    "terminal-capture"
    "transmission"
  ];

  semanticBundleSubjects = [
    "desktop"
    "dev"
  ];

  manualSpecNames = [
    "dev-shell"
    "dev-git"
    "dev-mcp-servers"
    "services-polylogue"
    "dev-editors-antigravity"
    "cli-polylogue"
    "desktop-mime"
    "desktop-hyprland"
    "desktop-audio"
    "desktop-common-apps"
    "desktop-terminal"
    "desktop-browser"
    "desktop-gaming"
    "networking-resolved-router-authority"
    "nextcloud-storage-wiring"
    "services-below"
    "services-power-watchdog"
    "services-transmission"
    "services-terminal-capture"
    "services-sentinel"
    "bundle-dev"
    "bundle-desktop"
    "minimal-no-features"
    "desktop-bluetooth-persistence"
    "paths-configured"
    "password-secrets-wiring"
    "router-config-evaluates"
    "backup-btrbk"
  ];

  featureSmokeSpecNames = map smokeName (
    builtins.filter (
      subject:
      builtins.elem "eval" (coverage.features.${subject}.layers or [ ])
      && !(builtins.elem subject semanticFeatureSubjects)
    ) (builtins.attrNames coverage.features)
  );

  serviceSmokeSpecNames = map smokeName (
    builtins.filter (
      subject:
      builtins.elem "eval" (coverage.services.${subject}.layers or [ ])
      && !(builtins.elem subject semanticServiceSubjects)
    ) (builtins.attrNames coverage.services)
  );

  bundleSmokeSpecNames = map smokeName (
    builtins.filter (
      subject:
      builtins.elem "eval" (coverage.bundles.${subject}.layers or [ ])
      && !(builtins.elem subject semanticBundleSubjects)
    ) (builtins.attrNames coverage.bundles)
  );

  allSpecNames = manualSpecNames ++ featureSmokeSpecNames ++ serviceSmokeSpecNames ++ bundleSmokeSpecNames;

  defaultSpecNames = [
    "dev-shell"
    "dev-git"
    "dev-mcp-servers"
    "services-polylogue"
    "desktop-terminal"
    "services-terminal-capture"
    "services-sentinel"
    "bundle-desktop"
    "router-config-evaluates"
    "backup-btrbk"
  ];

  heavySpecNames = builtins.filter (name: !(builtins.elem name defaultSpecNames)) allSpecNames;

  runtimeCheckNames = [
    "backup-borg-hook-runtime"
    "cli-polylogue-runtime"
    "cli-task-tracking-runtime"
    "dev-agent-restore-runtime"
    "dev-git-runtime"
    "dev-languages-runtime"
    "forge-pty"
    "forge-runtime"
    "terminal-capture-runtime"
    "terminal-capture-runtime-failure"
  ];

  vmCheckNames = [
    "below-vm"
    "polylogue-vm"
    "sentinel-vm"
    "transmission-vm"
  ];

  hostBuildCheckNames = [
    "host-sinnix-prime-build"
    "host-sinnix-ethereal-build"
  ];

  defaultAuxCheckNames = [
    "coverage-manifest"
    "router-config-build"
  ];

  defaultCheckNames = map (name: "nixos-${name}") defaultSpecNames ++ defaultAuxCheckNames;
  heavyCheckNames = map (name: "nixos-${name}") heavySpecNames ++ runtimeCheckNames ++ vmCheckNames ++ hostBuildCheckNames;
in
{
  inherit
    semanticFeatureSubjects
    semanticServiceSubjects
    semanticBundleSubjects
    manualSpecNames
    featureSmokeSpecNames
    serviceSmokeSpecNames
    bundleSmokeSpecNames
    allSpecNames
    defaultSpecNames
    heavySpecNames
    runtimeCheckNames
    vmCheckNames
    hostBuildCheckNames
    defaultAuxCheckNames
    defaultCheckNames
    heavyCheckNames
    ;
}
