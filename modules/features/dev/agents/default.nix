# Agent CLI wrappers + MCP server registry — regrouped subtree.
#
# Two independent features live here (sinnix.features.dev.agentTools and
# sinnix.features.dev.mcp-servers), each with its own option namespace, so
# this is an explicit imports list rather than a further mkAutoImports
# recursion: the domain-split helper files (backends.nix, mcp-tools.nix,
# client-profiles.nix, serena.nix, browser.nix, hooks.nix, skill-farm.nix)
# are plain-nix
# helpers consumed via `import`, not standalone modules — only clis.nix and
# mcp.nix are real modules.
{
  imports = [
    ./clis.nix
    ./mcp.nix
  ];
}
