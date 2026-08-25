# Config-derived Polylogue hook adapter. Plain helper, not a module.
{
  lib,
  pkgs,
  dataDir,
  polylogueHook,
}:
pkgs.writeShellScriptBin "sinnix-polylogue-hook" ''
  set -euo pipefail
  exec ${polylogueHook}/bin/polylogue-hook "$@" --sidecar-dir ${lib.escapeShellArg "${dataDir}/hooks"}
''
