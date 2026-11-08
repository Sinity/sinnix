# Sinex MCP provider backport

The workstation daemon runs Sinex `ba6cf2c601db2849e34c8c3c22019ec1bba09eb4`:
schema-2 revision `a081818b6` plus two commits, bounded commit-log and window
page reads and size-fitting of confirmed-stream messages (neither changes
`sinexctl` code, so this patch still applies). The MCP provider builds only `sinexctl` from that same input with
`read-only-mcp.patch`. The patch backports the Access-derived read annotations
and object-only structured replies merged upstream as
`0d4ecc08c97d5c840bce1fb1cb138fa038477d8f` (PR 2969). It retains the data notice.

The package exposes its upstream revision and SHA-256 patch digest separately
through `upstreamRevision` and `mcpPatchHash`. Its pin assertion requires an
explicit decision when the shared input moves. Only `sinnix-mcp-sinex` consumes
this package; the NixOS module, daemon package and ordinary system CLI retain
the unpatched input. The output asserts that it contains only `sinexctl`.

Remove this package, patch and script dependency when a reviewed deployment
moves the daemon through the full schema migration to a Sinex revision
containing the upstream fix. Restore the provider to the deployed system CLI
and prove the installed MCP read route against that daemon before retiring it.
