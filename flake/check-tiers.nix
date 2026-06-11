{ lib }:
let
  coverage = import ./test-coverage.nix;
  smokeName = subject: "smoke-" + lib.replaceStrings [ "." ] [ "-" ] subject;
  semanticFeatureSubjects = [
    "cli.polylogue"
    "desktop.activitywatch"
    "desktop.audio"
    "desktop.base"
    "desktop.browser"
    "desktop.common-apps"
    "desktop.gaming"
    "desktop.hyprland"
    "desktop.mime"
    "desktop.terminal"
    "desktop.ui"
    "dev.agentTools"
    "dev.editors"
    "dev.git"
    "dev.mcp-servers"
    "dev.shell"
    "dev.workbench"
  ];
  semanticServiceSubjects = [
    "below"
    "airvpn-seed"
    "machine-telemetry"
    "polylogue"
    "terminal-capture"
    "transmission"
  ];
  manualSpecNames = [
    "dev-agent-tools"
    "dev-shell"
    "dev-git"
    "dev-workbench"
    "dev-mcp-servers"
    "services-polylogue"
    "services-polylogue-manual-start"
    "dev-editors-antigravity"
    "cli-polylogue"
    "desktop-mime"
    "desktop-hyprland"
    "desktop-base"
    "desktop-audio"
    "desktop-common-apps"
    "desktop-terminal"
    "desktop-browser"
    "desktop-ui"
    "desktop-activitywatch"
    "desktop-activitywatch-manual-start"
    "desktop-gaming"
    "networking-resolved-router-authority"
    "services-airvpn-seed"
    "services-airvpn-seed-manual-start"
    "services-lynchpin"
    "storage-rclone-backup-wiring"
    "services-below"
    "services-machine-telemetry"
    "services-transmission"
    "services-transmission-manual-start"
    "services-terminal-capture"
    "services-sinex-delayed-runtime"
    "host-sinnix-prime-storage-discard-policy"
    "host-sinnix-prime-observability-policy"
    "minimal-no-features"
    "core-performance-policy"
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
  allSpecNames = manualSpecNames ++ featureSmokeSpecNames ++ serviceSmokeSpecNames;
  defaultSpecNames = [
    "dev-shell"
    "dev-git"
    "dev-mcp-servers"
    "services-machine-telemetry"
    "services-polylogue"
    "desktop-activitywatch"
    "desktop-activitywatch-manual-start"
    "desktop-terminal"
    "desktop-base"
    "desktop-ui"
    "services-terminal-capture"
    "services-sinex-delayed-runtime"
    "host-sinnix-prime-storage-discard-policy"
    "host-sinnix-prime-observability-policy"
    "core-performance-policy"
    "router-config-evaluates"
    "backup-btrbk"
  ];
  heavySpecNames = builtins.filter (name: !(builtins.elem name defaultSpecNames)) allSpecNames;
  runtimeCheckNames = [
    "backup-borg-hook-runtime"
    "cli-polylogue-runtime"
    "cli-task-tracking-runtime"
    "dev-agent-tools-pty"
    "dev-agent-tools-runtime"
    "dev-git-runtime"
    "dev-languages-runtime"
    "sinnix-observe-runtime"
    "terminal-capture-runtime"
    "terminal-capture-runtime-failure"
  ];
  vmCheckNames = [
    "below-vm"
    "polylogue-vm"
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
  heavyCheckNames =
    map (name: "nixos-${name}") heavySpecNames
    ++ runtimeCheckNames
    ++ vmCheckNames
    ++ hostBuildCheckNames;
in
{
  inherit
    semanticFeatureSubjects
    semanticServiceSubjects
    manualSpecNames
    featureSmokeSpecNames
    serviceSmokeSpecNames
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
