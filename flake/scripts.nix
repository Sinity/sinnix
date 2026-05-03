/*
  Script registry — director only.

  All packaged scripts under `scripts/` opt in via `# @sinnix-package`
  frontmatter (description + runtimeInputs); discovery code in
  `flake/script-discovery.nix` walks the directory and constructs the
  package set.

  Scripts launched directly by Hyprland keybindings or sourced by the
  shell declare `# @sinnix-package: skip`.

  This file additionally exposes the few non-script packages that wrap
  external flake outputs (lynchpin/polylogue Pythons) and the npm-vendor
  packages (mcp-firecrawl, ccusage).
*/
{ inputs, pkgs }:
let
  inherit (pkgs) lib;

  discovery = import ./script-discovery.nix { inherit lib pkgs; };
  discovered = discovery.discover (inputs.self + "/scripts");

  registry = discovered.registry;
  scriptPackages = lib.mapAttrs (_: v: v.package) registry;

  mkSanitizedPythonWrapper =
    {
      name,
      target,
    }:
    pkgs.writeShellScriptBin name ''
      set -euo pipefail
      unset PYTHONPATH PYTHONHOME PYTHONBREAKPOINT PYTHONUSERBASE VIRTUAL_ENV
      exec ${target} "$@"
    '';

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
      inherit
        pname
        version
        src
        npmDepsHash
        ;
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

  externalPackages = {
    lynchpin-python = pkgs.writeShellScriptBin "lynchpin-python" ''
      set -euo pipefail
      exec ${inputs.lynchpin.packages.${pkgs.stdenv.hostPlatform.system}.api-python}/bin/python "$@"
    '';

    polylogue-cli = mkSanitizedPythonWrapper {
      name = "polylogue";
      target = "${inputs.polylogue.packages.${pkgs.stdenv.hostPlatform.system}.default}/bin/polylogue";
    };

    polylogue-python = mkSanitizedPythonWrapper {
      name = "polylogue-python";
      target = "${inputs.polylogue.packages.${pkgs.stdenv.hostPlatform.system}.api-python}/bin/python";
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

  packageSet = scriptPackages // externalPackages;
in
{
  packages = scriptPackages;
  inherit packageSet;
  inherit registry;
  list = lib.attrNames registry;
}
