# ========================================
# PACKAGES: Custom packages for sinnix
# ========================================
#
# Script packages are defined in scripts.nix registry.
# This file re-exports them and can add non-script packages.
{ inputs, ... }:
{
  perSystem =
    { pkgs, ... }:
    let
      scriptRegistry = import ./scripts.nix { inherit inputs pkgs; };
      mkNodeCliPackage =
        {
          pname,
          version,
          src,
          packagePath,
          entrypoint,
          npmDepsHash,
        }:
        pkgs.buildNpmPackage {
          inherit pname version src npmDepsHash;
          dontNpmBuild = true;
          dontNpmPrune = true;

          installPhase = ''
            runHook preInstall

            libexec="$out/libexec/${pname}"
            mkdir -p "$libexec" "$out/bin"
            cp -r node_modules package.json package-lock.json "$libexec/"
            makeWrapper ${pkgs.nodejs}/bin/node "$out/bin/${pname}" \
              --add-flags "$libexec/node_modules/${packagePath}/${entrypoint}"

            runHook postInstall
          '';

          meta = {
            description = "${pname} packaged for sinnix MCP usage";
            mainProgram = pname;
          };
        };

      customPackages = {
        mcp-context7 = mkNodeCliPackage {
          pname = "mcp-context7";
          version = "2.1.4";
          src = ./npm/context7-mcp;
          packagePath = "@upstash/context7-mcp";
          entrypoint = "dist/index.js";
          npmDepsHash = "sha256-Tlo/IcyETB6iEqo9MYN937TAS3DmHCSmfBDwa+4HzDM=";
        };

        mcp-firecrawl = mkNodeCliPackage {
          pname = "mcp-firecrawl";
          version = "3.10.3";
          src = ./npm/firecrawl-mcp;
          packagePath = "firecrawl-mcp";
          entrypoint = "dist/index.js";
          npmDepsHash = "sha256-bz3EVlVQNOeS5g9qvO1+5OIcMNxVQ+oLrwA9j9ZmqEY=";
        };

        ccusage = mkNodeCliPackage {
          pname = "ccusage";
          version = "18.0.10";
          src = ./npm/ccusage;
          packagePath = "ccusage";
          entrypoint = "dist/index.js";
          npmDepsHash = "sha256-/duhx34Iiq+7ZOaRTTAWChbGjJhxiVvWOoaLJsH2USc=";
        };
      };
    in
    {
      # Export all script packages from registry
      packages = scriptRegistry.packages // customPackages;
    };
}
