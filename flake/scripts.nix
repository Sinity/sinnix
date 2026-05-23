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

  mkSanitizedPythonWrappers =
    {
      name,
      commands,
    }:
    pkgs.symlinkJoin {
      inherit name;
      paths = lib.mapAttrsToList (
        commandName: target:
        mkSanitizedPythonWrapper {
          name = commandName;
          inherit target;
        }
      ) commands;
    };

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

  polylogueSrc = inputs.polylogue.packages.${pkgs.stdenv.hostPlatform.system}.default;

  externalPackages = {
    lynchpin-python = pkgs.writeShellScriptBin "lynchpin-python" ''
      set -euo pipefail
      exec ${inputs.lynchpin.packages.${pkgs.stdenv.hostPlatform.system}.api-python}/bin/python "$@"
    '';

    lynchpin-cli = mkSanitizedPythonWrappers {
      name = "lynchpin-cli";
      commands = {
        lynchpin-mcp = "${
          inputs.lynchpin.packages.${pkgs.stdenv.hostPlatform.system}.default
        }/bin/lynchpin-mcp";
      };
    };

    # polylogue's own postFixup already wraps all CLI binaries and the api-python
    # interpreter with PYTHONPATH/PYTHONHOME/… unset. Use symlink trees to expose
    # only the intended commands per package.
    polylogue-cli = pkgs.runCommand "polylogue-cli" { } ''
      mkdir -p "$out/bin"
      ln -s "${polylogueSrc}/bin/polylogue" "$out/bin/polylogue"
      ln -s "${polylogueSrc}/bin/polylogue-mcp" "$out/bin/polylogue-mcp"
    '';

    polylogue-python = pkgs.runCommand "polylogue-python" { } ''
      mkdir -p "$out/bin"
      ln -s "${
        inputs.polylogue.packages.${pkgs.stdenv.hostPlatform.system}.api-python
      }/bin/python" "$out/bin/polylogue-python"
    '';

    polylogued = pkgs.runCommand "polylogued" { } ''
      mkdir -p "$out/bin"
      ln -s "${polylogueSrc}/bin/polylogued" "$out/bin/polylogued"
    '';

    mcp-firecrawl = mkNodeCliPackage {
      pname = "mcp-firecrawl";
      version = "3.10.3";
      src = ./npm/firecrawl-mcp;
      packagePath = "firecrawl-mcp";
      entrypoint = "dist/index.js";
      npmDepsHash = "sha256-bz3EVlVQNOeS5g9qvO1+5OIcMNxVQ+oLrwA9j9ZmqEY=";
    };

    mcp-chrome-devtools = mkNodeCliPackage {
      pname = "mcp-chrome-devtools";
      version = "0.25.0";
      src = ./npm/chrome-devtools-mcp;
      packagePath = "chrome-devtools-mcp";
      entrypoint = "build/src/bin/chrome-devtools-mcp.js";
      npmDepsHash = "sha256-yGbzAtsbFBilXwTBL+dXkH2NM6tzOu7wnowE/z9WwQo=";
    };

    ccusage = mkNodeCliPackage {
      pname = "ccusage";
      version = "18.0.10";
      src = ./npm/ccusage;
      packagePath = "ccusage";
      entrypoint = "dist/index.js";
      npmDepsHash = "sha256-/duhx34Iiq+7ZOaRTTAWChbGjJhxiVvWOoaLJsH2USc=";
    };

    sinnix-observe = pkgs.callPackage ../pkgs/sinnix-observe/pkg.nix { };

    # Python port of sinnix-sentinel (Phase G). Ships side-by-side with the
    # bash script; the systemd unit in modules/services/sentinel.nix is
    # intentionally NOT redirected here. Promotion is a separate operational
    # step after a 24h observe-only validation window.
    sinnix-sentinel-py = pkgs.callPackage ../pkgs/sinnix-sentinel/pkg.nix { };
  };

  packageSet = scriptPackages // externalPackages;
in
{
  packages = scriptPackages;
  inherit packageSet;
  inherit registry;
  list = lib.attrNames registry;
}
