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
  mcpLynchpinBin = mkMcpWrapper "mcp-lynchpin" {
    command = "${scriptPkgs.lynchpin-python}/bin/lynchpin-python";
    args = [
      "-m"
      "lynchpin.mcp.cli"
    ];
    # A managed launcher must not inherit retired roots from an older session.
    # Foundation owns these paths; standalone source overrides stay separate.
    runtimeEnv = {
      inherit (config.environment.variables)
        LYNCHPIN_REPO_ROOT
        SINEX_ROOT
        POLYLOGUE_ROOT
        RAWLOG_FILE
        ;
      LYNCHPIN_LOCAL_ROOT = "${config.environment.variables.LYNCHPIN_REPO_ROOT}/.lynchpin";
    }
    // lib.filterAttrs (
      name: _:
      builtins.elem name [
        "LYNCHPIN_CHISEL_CACHE_ROOT"
        "LYNCHPIN_CHISEL_SCRATCH_ROOT"
      ]
    ) config.environment.variables;
  };
  mcpPolylogueBin = pkgs.writeShellScriptBin "mcp-polylogue" ''
    set -euo pipefail
    # The configured service data directory is the sole archive-root owner.
    export POLYLOGUE_ARCHIVE_ROOT=${lib.escapeShellArg config.sinnix.services.polylogue.dataDir}
    exec ${scriptPkgs.polylogue-cli}/bin/polylogue-mcp "$@"
  '';
  # The user-facing files stay tiny out-of-store launchers, while the gateway
  # consumes the identical store-backed commands directly.
  mcpLynchpinText = ''
    #!${pkgs.runtimeShell}
    exec ${mcpLynchpinBin}/bin/mcp-lynchpin "$@"
  '';
  mcpPolylogueText = ''
    #!${pkgs.runtimeShell}
    exec ${mcpPolylogueBin}/bin/mcp-polylogue "$@"
  '';
in
{
  inherit
    mkRuntimeSecretExports
    mkMcpWrapper
    mcpFirecrawlBin
    mcpLynchpinBin
    mcpPolylogueBin
    mcpLynchpinText
    mcpPolylogueText
    ;
}
