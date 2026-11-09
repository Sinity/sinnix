# One archive binding for the CLI, daemon, hooks, browser host and MCP server.
{
  lib,
  pkgs,
  inputs,
  config,
}:
let
  cfg = config.sinnix.services.polylogue;
  ports = import ../../flake/data/ports.nix;
  dataHome =
    if cfg.sinex.mode == "primary" then "${cfg.liveRoot}/sinex-data" else "${cfg.liveRoot}/data";
  package = inputs.polylogue-rewrite.packages.${pkgs.stdenv.hostPlatform.system}.polylogue;
  # Spools live on the root disk, not /realm: each hook line is synced before
  # the hook returns, and a sync behind /realm's bulk writeback stalls for
  # hundreds of milliseconds. modules/persistence.nix persists the directory.
  stateHome = "${config.users.users.${config.sinnix.user.name}.home}/.local/state";
in
pkgs.writeShellScriptBin "polylogue" ''
  export POLYLOGUE_HTTP_PORT=${toString ports.polylogue.web}
  export XDG_DATA_HOME=${lib.escapeShellArg dataHome}
  export XDG_STATE_HOME=${lib.escapeShellArg stateHome}
  unset POLYLOGUE_ARCHIVE POLYLOGUE_HOME
  exec ${package}/bin/polylogue "$@"
''
