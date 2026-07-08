# Generic MCP server tool wrappers: the shared runtime-secret-export
# builder, the Firecrawl MCP wrapper, and the Codebase Memory MCP web UI
# launcher. Plain helper (not a NixOS module) — imported directly by
# mcp.nix's configFn, not picked up by auto-import.
{
  lib,
  pkgs,
  scriptPkgs,
  config,
}:
let
  firecrawlSecretPath = lib.attrByPath [ "sinnix" "secrets" "paths" "firecrawl-api-key" ] null config;
  mkRuntimeSecretExports =
    secretEnv:
    lib.concatStringsSep "\n" (
      lib.mapAttrsToList (envName: secretPath: ''
        if [ -z "''${${envName}:-}" ] && [ -r ${secretPath} ]; then
          export ${envName}="$(<${secretPath})"
        fi
      '') secretEnv
    );
  mkMcpWrapper =
    name:
    {
      command,
      args ? [ ],
      runtimeEnv ? { },
      runtimeSecretEnv ? { },
    }:
    pkgs.writeShellScriptBin name ''
      set -euo pipefail
      ${lib.concatStringsSep "\n" (
        lib.mapAttrsToList (envName: value: "export ${envName}=${lib.escapeShellArg value}") runtimeEnv
      )}
      ${mkRuntimeSecretExports runtimeSecretEnv}
      exec ${lib.escapeShellArgs ([ command ] ++ args)} "$@"
    '';
  mcpFirecrawlBin = mkMcpWrapper "mcp-firecrawl" {
    command = "${scriptPkgs.mcp-firecrawl}/bin/mcp-firecrawl";
    runtimeSecretEnv = lib.optionalAttrs (firecrawlSecretPath != null) {
      FIRECRAWL_API_KEY = firecrawlSecretPath;
    };
  };
  codebaseMemoryUiLauncher = pkgs.writeShellScript "codebase-memory-ui" ''
    set -euo pipefail
    export CBM_CACHE_DIR="''${CBM_CACHE_DIR:-$HOME/.local/share/codebase-memory-mcp}"
    mkdir -p "$CBM_CACHE_DIR"
    exec ${
      scriptPkgs."codebase-memory-mcp"
    }/bin/codebase-memory-mcp --ui=true --port=9749 < <(${pkgs.coreutils}/bin/sleep infinity)
  '';
  # `home.file` text for the Lynchpin/Polylogue/Sinex MCP wrappers. These are
  # plain launch scripts (no HM-scoped `config` needed) so they live here
  # alongside the other generic MCP tool wrappers rather than inline in
  # mcp.nix's home-manager body.
  mcpLynchpinText = ''
    #!${pkgs.runtimeShell}
    set -euo pipefail
    export LYNCHPIN_REPO_ROOT=/realm/project/sinity-lynchpin
    export LYNCHPIN_LOCAL_ROOT=/realm/project/sinity-lynchpin/.lynchpin
    export PYTHONPATH="$LYNCHPIN_REPO_ROOT''${PYTHONPATH:+:$PYTHONPATH}"
    exec ${scriptPkgs.lynchpin-python}/bin/lynchpin-python -m lynchpin.mcp.cli "$@"
  '';
  mcpPolylogueText = ''
    #!${pkgs.runtimeShell}
    set -euo pipefail
    # The polylogue repo's .claude/settings.json pins
    # POLYLOGUE_ARCHIVE_ROOT to the cloud-lane fixture
    # (/tmp/polylogue-archive) for CI/cloud agents. That env leaks into
    # locally-launched MCP servers and would point recall at an empty
    # archive. Drop any leaked override that doesn't resolve to a real
    # directory (not just the one known cloud-lane literal — 2026-07-06:
    # an exact-string check alone left a long-lived MCP server stuck
    # pointing at the cloud fixture for its entire process lifetime
    # whenever it had been spawned with the leak present; checking
    # existence instead of one hardcoded path is the same fix generalized,
    # though it still can't un-stick a server process already running with
    # the leak baked into its own inherited environment — that needs the
    # MCP connection itself restarted) so recall resolves the operator's
    # real live archive (an intentional override to any real path is
    # preserved).
    if [ -n "''${POLYLOGUE_ARCHIVE_ROOT:-}" ] && [ ! -d "''${POLYLOGUE_ARCHIVE_ROOT}" ]; then
      unset POLYLOGUE_ARCHIVE_ROOT
    fi
    exec ${scriptPkgs.polylogue-cli}/bin/polylogue-mcp "$@"
  '';
in
{
  inherit
    mkRuntimeSecretExports
    mkMcpWrapper
    mcpFirecrawlBin
    codebaseMemoryUiLauncher
    mcpLynchpinText
    mcpPolylogueText
    ;
}
