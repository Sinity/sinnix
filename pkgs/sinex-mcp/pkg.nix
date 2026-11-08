# Temporary provider-only backport; retire with the reviewed Sinex migration.
{
  upstream,
  sourceRevision,
}:
assert sourceRevision == "ba6cf2c601db2849e34c8c3c22019ec1bba09eb4";
upstream.overrideAttrs (old: {
  pname = "sinex-mcp-cli";
  patches = (old.patches or [ ]) ++ [ ./read-only-mcp.patch ];
  cargoBuildFlags = [
    "-p"
    "sinexctl"
  ];
  cargoTestFlags = [
    "-p"
    "sinexctl"
    "--bin"
    "sinexctl"
    "mcp::tests"
  ];
  checkFlags = [ ];
  # The selected Cargo build produces only this CLI; fail if the upstream
  # install hook ever broadens the provider package to include the daemon.
  postInstall = (old.postInstall or "") + ''
    test -x "$out/bin/sinexctl"
    test "$(find "$out/bin" -mindepth 1 -maxdepth 1 | wc -l)" -eq 1
  '';
  passthru = (old.passthru or { }) // {
    upstreamRevision = sourceRevision;
    mcpPatchHash = builtins.hashFile "sha256" ./read-only-mcp.patch;
  };
})
