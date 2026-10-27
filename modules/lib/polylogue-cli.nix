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
in
pkgs.writeShellScriptBin "polylogue" ''
  export POLYLOGUE_HTTP_PORT=${toString ports.polylogue.web}
  export XDG_DATA_HOME=${lib.escapeShellArg dataHome}
  export XDG_STATE_HOME=${lib.escapeShellArg "${cfg.liveRoot}/state"}
  unset POLYLOGUE_ARCHIVE POLYLOGUE_HOME
  exec ${package}/bin/polylogue "$@"
''
