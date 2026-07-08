# Chrome DevTools MCP wrappers and the desktop-control-plane script bundle
# (chrome/hypr/keyboard/kitty/screenshot control). Plain helper (not a
# NixOS module) — imported directly by mcp.nix's configFn, not picked up by
# auto-import.
{
  lib,
  pkgs,
  scriptPkgs,
  inputs,
}:
let
  # Chrome DevTools MCP — vendored npm package built via mkNodeCliPackage.
  # Attaches to the user's running Chrome on the loopback debug port
  # (configured by modules/features/desktop/browser.nix:47). Private agent
  # browsers use mcp-chrome-devtools-private instead of this live profile.
  mcpChromeDevtoolsBin = pkgs.writeShellScriptBin "mcp-chrome-devtools" ''
    set -euo pipefail
    target="''${SINNIX_CHROME_DEVTOOLS_URL-http://127.0.0.1:9222}"
    if [ -z "$target" ]; then
      echo "SINNIX_CHROME_DEVTOOLS_URL must name a Chrome DevTools endpoint" >&2
      exit 2
    fi
    exec ${scriptPkgs.mcp-chrome-devtools}/bin/mcp-chrome-devtools \
      --browserUrl "$target" \
      "$@"
  '';
  # Agent-owned Chrome DevTools MCP. This gives agents the same DevTools tool
  # shape as the user's live Chrome, but against a private persistent profile
  # seeded from live Chrome state before launch. It stays separate from the
  # shell CDP helper's private profile so concurrent MCP and shell browser
  # sessions cannot fight over a Chrome profile lock. It is headless by
  # default; set SINNIX_AGENT_CHROME_HEADLESS=0 when a visible private
  # browser window is desired for operator inspection.
  mcpChromeDevtoolsPrivateBin = pkgs.writeShellScriptBin "mcp-chrome-devtools-private" ''
    set -euo pipefail
    export SINNIX_MCP_CHROME_DEVTOOLS_BIN=${lib.escapeShellArg "${scriptPkgs.mcp-chrome-devtools}/bin/mcp-chrome-devtools"}
    exec ${scriptPkgs.sinnix-mcp-chrome-devtools-private}/bin/sinnix-mcp-chrome-devtools-private "$@"
  '';
  mcpChromeDevtoolsPrivateVisibleBin = pkgs.writeShellScriptBin "mcp-chrome-devtools-private-visible" ''
    set -euo pipefail
    export SINNIX_AGENT_CHROME_HEADLESS=0
    exec ${mcpChromeDevtoolsPrivateBin}/bin/mcp-chrome-devtools-private "$@"
  '';
  desktopControlScripts = inputs.self + "/dots/_ai/skills/desktop-control-plane/scripts";
in
{
  inherit
    mcpChromeDevtoolsBin
    mcpChromeDevtoolsPrivateBin
    mcpChromeDevtoolsPrivateVisibleBin
    desktopControlScripts
    ;
}
