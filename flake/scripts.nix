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

  inherit (discovered) registry;
  scriptPackages = lib.mapAttrs (_: v: v.package) registry // {
    # Generated meta-CLI front door over every packaged script above. Kept
    # in scriptPackages (not externalPackages) because it is derived
    # entirely from `registry`, not from an external flake input.
    sinnix = import ./cli-dispatcher.nix { inherit lib pkgs registry; };
  };
  runtimeDefaults = import ./data/runtime-defaults.nix { inherit lib; };
  mcpRegistry = import ./data/mcp-registry.nix { inherit lib; };
  sharedAgentSkills = import ./data/shared-agent-skills.nix;
  agentEnvironmentData = pkgs.writeText "sinnix-agent-environment-data.json" (builtins.toJSON {
    profiles = lib.concatMap (
      profile:
      map (client: {
        name = profile;
        inherit client;
        tiers = mcpRegistry.profileTiers.${profile};
        servers = lib.attrNames (mcpRegistry.selectClientServersForProfile profile client);
      }) [ "claude" "codex" "gemini" "antigravity" "hermes" ]
    ) [ "lean" "evidence" "full" "browser" "orchestrate" "antigravity" ];
    servers = lib.mapAttrsToList (name: server: {
      inherit name;
      inherit (server) tier transport clients;
      command = server.command or null;
      url = server.url or null;
    }) mcpRegistry.registry;
    skills = sharedAgentSkills;
  });
  defaultRuntimeInventoryJson = builtins.toJSON (
    runtimeDefaults.mkInventory {
      hostname = "sinnix-fallback";
      surfaces = runtimeDefaults.baseSurfaces;
    }
  );
  agentGatewayPackage = pkgs.callPackage ../pkgs/sinnix-agent-gateway/pkg.nix { };

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
    # bd needs the dolt binary on PATH for sql-server mode (per-project server,
    # auto-started on demand). Embedded mode serializes every invocation on a
    # process-exclusive lock — under multi-agent fanouts that convoys for
    # minutes, and it pays ~2.3s engine startup per call vs ~65ms as a server
    # client. Wrap rather than add dolt globally so every bd consumer (hooks,
    # devshells, agent lanes) gets server capability unconditionally.
    beads =
      let
        # No local patches: beads-server-auto-import-empty-check.patch was
        # dropped at the v1.0.4 -> v1.1.2 bump. Upstream now carries its own
        # guard for the same defect (a stale issues.jsonl re-imposed over
        # newer Dolt rows on every mutating command after a branch switch) --
        # see the GetStatistics emptiness guard and its "cf. PR #3630"
        # comment in cmd/bd/auto_import_upgrade.go. Our patch no longer
        # applies cleanly against the rewritten function and produced a
        # non-compiling tree, which is itself the signal that it is obsolete.
        beadsBase = pkgs.callPackage (inputs.beads + "/default.nix") {
          self = inputs.beads;
          buildGoModule = pkgs.buildGo126Module;
        };
      in
      pkgs.symlinkJoin {
        name = "beads-with-dolt";
        paths = [ beadsBase ];
        nativeBuildInputs = [ pkgs.makeWrapper ];
        postBuild = ''
          wrapProgram $out/bin/bd --prefix PATH : ${pkgs.lib.makeBinPath [ pkgs.dolt ]}
        '';
      };

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

    # polylogue's own postFixup wraps polylogue/polylogued/polylogue-mcp with
    # PYTHONPATH/PYTHONHOME/… unset (it does NOT cover polylogue-hook, which
    # ships as an unwrapped console_scripts entry point — a narrower version
    # of the same leak class as polylogue-xikl, since hook subprocesses run
    # from arbitrary agent-devshell environments). Use symlink trees to
    # expose only the intended commands per package.
    polylogue-cli = pkgs.runCommand "polylogue-cli" { } ''
      mkdir -p "$out/bin"
      ln -s "${polylogueSrc}/bin/polylogue" "$out/bin/polylogue"
      ln -s "${polylogueSrc}/bin/polylogue-mcp" "$out/bin/polylogue-mcp"
      ln -s "${polylogueSrc}/bin/polylogue-hook" "$out/bin/polylogue-hook"
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

    sinnix-agent-gateway = agentGatewayPackage;
    sinnix-agent-control-mcp = pkgs.writeShellApplication {
      name = "sinnix-agent-control-mcp";
      runtimeInputs = [ agentGatewayPackage ];
      text = ''
        config="''${SINNIX_AGENT_GATEWAY_CONFIG:-/etc/sinnix/agent-gateway.json}"
        exec sinnix-agent-gateway --config "$config" --profile local-agent-control serve
      '';
      meta.description = "Local-agent-control profile of the shared Sinnix MCP gateway";
    };
    tunnel-client = pkgs.callPackage ../pkgs/tunnel-client { };

    sinnix-observe = pkgs.callPackage ../pkgs/sinnix-observe/pkg.nix {
      inherit defaultRuntimeInventoryJson;
    };

    sinnix-ops-reducer = pkgs.callPackage ../pkgs/sinnix-ops-reducer/pkg.nix { };

    sinnix-quota = pkgs.callPackage ../pkgs/sinnix-quota/pkg.nix { };

    # NOTE: depends on pkgs/sinnix-capture/ (sinnix-mufn, the shared
    # sinnix-capture-v1 envelope writer lib) existing as a sibling package --
    # not yet merged onto this branch as of sinnix-fp9v. sinnix-capture-a11y's
    # pkg.nix references it via a relative `../sinnix-capture/pkg.nix` path,
    # so this line (and the a11y module that consumes it) will resolve once
    # sinnix-mufn lands; until then `nix eval` on this attribute fails with a
    # missing-path error for pkgs/sinnix-capture, not a bug in this package.
    sinnix-capture-a11y = pkgs.callPackage ../pkgs/sinnix-capture-a11y/pkg.nix { };

    sinnix-agent-environment-doc = pkgs.writeShellApplication {
      name = "sinnix-agent-environment-doc";
      runtimeInputs = [ pkgs.bash pkgs.coreutils pkgs.findutils pkgs.gawk pkgs.jq pkgs.ripgrep ];
      text = ''
        exec ${pkgs.bash}/bin/bash ${pkgs.writeText "sinnix-agent-environment-doc-source" (builtins.readFile ../scripts/sinnix-agent-environment-doc)} \
          --data ${agentEnvironmentData} \
          --skills-root "''${SINNIX_AGENT_SKILLS_ROOT:-$PWD/dots/_ai/skills}" \
          --agents-root "''${SINNIX_AGENT_DEFS_ROOT:-$PWD/dots/claude/agents}" \
          "$@"
      '';
      meta.description = "Render the generated Sinnix agent environment reference";
    };
  };

  packageSet = scriptPackages // externalPackages;
in
{
  packages = scriptPackages // { inherit (externalPackages) sinnix-agent-environment-doc; };
  inherit packageSet;
  inherit registry;
  list = lib.attrNames registry;
}
