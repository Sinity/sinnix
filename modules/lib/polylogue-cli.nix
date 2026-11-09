# One archive binding for the CLI, daemon, hooks, browser host and MCP server.
#
# A compiled wrapper, not a shell script: hooks start this command twice per
# agent tool call, and two bash layers (this binding and the package's own
# wrapProgram) cost more than Polylogue's work. The package's wrapper only
# prefixes git onto PATH, so when it is present this wrapper execs the binary
# behind it and adds git itself.
{
  lib,
  pkgs,
  inputs,
  config,
}:
let
  cfg = config.sinnix.services.polylogue;
  inherit (cfg) dataHome;
  package = inputs.polylogue-rewrite.packages.${pkgs.stdenv.hostPlatform.system}.polylogue;
  # Spools live on the root disk, not /realm: each hook line is synced before
  # the hook returns, and a sync behind /realm's bulk writeback stalls for
  # hundreds of milliseconds. modules/persistence.nix persists the directory.
  stateHome = "${config.users.users.${config.sinnix.user.name}.home}/.local/state";
in
pkgs.runCommand "polylogue" { nativeBuildInputs = [ pkgs.makeBinaryWrapper ]; } ''
  target=${package}/bin/polylogue
  extra=()
  if [ -x ${package}/bin/.polylogue-wrapped ]; then
    target=${package}/bin/.polylogue-wrapped
    extra=(--prefix PATH : ${lib.makeBinPath [ pkgs.git ]})
  fi
  mkdir -p $out/bin
  makeBinaryWrapper "$target" $out/bin/polylogue \
    --inherit-argv0 \
    --set XDG_DATA_HOME ${lib.escapeShellArg dataHome} \
    --set XDG_STATE_HOME ${lib.escapeShellArg stateHome} \
    --unset POLYLOGUE_ARCHIVE \
    --unset POLYLOGUE_HOME \
    "''${extra[@]}"
''
