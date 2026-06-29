{ lib }:
let
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
  defaultAuxCheckNames = [ "router-config-build" ];
in
{
  inherit
    runtimeCheckNames
    vmCheckNames
    hostBuildCheckNames
    defaultAuxCheckNames
    ;
  defaultCheckNames = defaultAuxCheckNames;
  heavyCheckNames =
    runtimeCheckNames
    ++ vmCheckNames
    ++ hostBuildCheckNames;
}
