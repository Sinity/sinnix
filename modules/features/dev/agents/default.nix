# Agent CLI wrappers + MCP server registry — regrouped subtree.
#
# Split out of the former modules/features/dev/{agent-tools,mcp-servers}.nix
# (sinnix-9u6, 2026-07-09). Two independent features live here
# (sinnix.features.dev.agentTools and sinnix.features.dev.mcp-servers), each
# with its own option namespace, so this directory is an explicit imports
# list rather than a further lib.sinnix.mkAutoImports recursion: the
# domain-split helper files below (backends.nix, mcp-tools.nix,
# client-profiles.nix, serena.nix, browser.nix, hooks.nix) are plain-nix
# helpers consumed via `import`, not standalone NixOS modules, and must not
# be auto-imported as such — only clis.nix and mcp.nix are real modules.
{
  imports = [
    ./clis.nix
    ./mcp.nix
  ];
}
