# Generic MCP server tool wrappers: the shared runtime-secret-export builder
# and Firecrawl MCP wrapper. Plain helper (not a NixOS module), imported
# directly by mcp.nix's configFn rather than picked up by auto-import.
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
    # The polylogue repo's .claude/settings.json pins POLYLOGUE_ARCHIVE_ROOT
    # to the cloud-lane fixture (/tmp/polylogue-archive), and that env leaks
    # into locally-launched MCP servers, pointing recall at an empty archive.
    # Drop any leaked override that does not resolve to a real directory —
    # testing existence rather than the one known literal also catches other
    # stale overrides, while preserving a deliberate override to a real path.
    # It cannot un-stick a server process already running with the leak in its
    # inherited environment; that needs the MCP connection restarted.
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
    mcpLynchpinText
    mcpPolylogueText
    ;
}
