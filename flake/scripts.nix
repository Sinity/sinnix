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

  sinnixCaptureLib = pkgs.callPackage ../pkgs/sinnix-capture/pkg.nix {
    sinnix-lib = externalPackages.sinnix-lib;
  };
  phoneAppPackage = pkgs.callPackage (inputs.phone-app + "/pkg.nix") { };
  discovery = import ./script-discovery.nix {
    inherit lib pkgs;
    siblingExtras = {
      sinnix-capture = sinnixCaptureLib;
      # Importable, not executable: named by a script's `pythonPackages`
      # frontmatter, which builds that script's shebang interpreter with the
      # library on sys.path. The same `@name` resolution as runtimeInputs,
      # a different consumer.
      sinnix-lib = externalPackages.sinnix-lib;
      # Shared pairwise/choice-set preference ranking engine (rank_core);
      # consumed by scripts/sinnix-rank the same way scripts import
      # @sinnix-lib.
      sinnix-rank-core = externalPackages.sinnix-rank-core;
      # Source lives in the steering workspace input; scripts naming
      # @sinnix-steer resolve to the wrapper below.
      sinnix-steer = externalPackages.sinnix-steer;
      # sinnix-phone-dispatcher moved out of scripts/ into a real Python
      # package (sinnix-svvz); scripts/sinnix-phone still names
      # @sinnix-phone-dispatcher in its own runtimeInputs and resolves here,
      # same pattern as sinnix-steer above.
      sinnix-phone-dispatcher = externalPackages.sinnix-phone-dispatcher;
      # Sinnix's bd, not nixpkgs'. A script naming bare `beads` in its
      # frontmatter gets pkgs.beads (1.0.3), whose `export` has no -C flag --
      # which failed as a usage dump swallowed by `|| true`.
      beads = externalPackages.beads;
      # sinnix-orient is a 3-line wrapper around `sinnix-ops-reducer orient`;
      # the reducer itself lives in externalPackages (a real Python package,
      # not a discovered script), so it resolves here the same way.
      sinnix-ops-reducer = externalPackages.sinnix-ops-reducer;
    };
  };
  discovered = discovery.discover (inputs.self + "/scripts");

  registry = discovered.registry // {
    # Same shape for the steering CLI: its source moved into the steering
    # workspace, but it remains an operator verb — keep it in the registry so
    # `sinnix help` lists it and `sinnix steer ...` dispatches.
    sinnix-steer = {
      description = "Personal steering store CLI — intentions with forecasts, activity menu, rituals";
      package = externalPackages.sinnix-steer;
      runtimeInputs = [ ];
      tier = "default";
      owner = "flake/scripts.nix";
      docs = "docs/steering.md";
    };
  };
  scriptPackages = lib.mapAttrs (_: v: v.package) registry // {
    # Generated meta-CLI front door over every packaged script above. Kept
    # in scriptPackages (not externalPackages) because it is derived
    # entirely from `registry`, not from an external flake input.
    sinnix = import ./cli-dispatcher.nix { inherit lib pkgs registry; };
  };
  runtimeDefaults = import ./data/runtime-defaults.nix { inherit lib; };
  mcpRegistry = import ./data/mcp-registry.nix { inherit lib; };
  sharedAgentSkills = import ./data/shared-agent-skills.nix;
  agentEnvironmentData = pkgs.writeText "sinnix-agent-environment-data.json" (
    builtins.toJSON {
      profiles =
        lib.concatMap
          (
            profile:
            map
              (client: {
                name = profile;
                inherit client;
                tiers = mcpRegistry.profileTiers.${profile};
                servers = lib.attrNames (mcpRegistry.selectClientServersForProfile profile client);
              })
              [
                "claude"
                "codex"
                "gemini"
                "antigravity"
                "hermes"
              ]
          )
          [
            "lean"
            "evidence"
            "full"
            "browser"
            "orchestrate"
            "antigravity"
          ];
      servers = lib.mapAttrsToList (name: server: {
        inherit name;
        inherit (server) tier transport clients;
        command = server.command or null;
        url = server.url or null;
      }) mcpRegistry.registry;
      skills = sharedAgentSkills;
    }
  );
  defaultRuntimeInventoryJson = builtins.toJSON (
    runtimeDefaults.mkInventory {
      hostname = "sinnix-fallback";
      surfaces = runtimeDefaults.baseSurfaces;
    }
  );
  sinnixMcpPackage = pkgs.callPackage ../pkgs/sinnix-mcp/pkg.nix { };
  sinnixdPackage = pkgs.callPackage ../pkgs/sinnixd/pkg.nix {
    sinnix-mcp = sinnixMcpPackage;
    sinnix-lib = externalPackages.sinnix-lib;
    beads = externalPackages.beads;
  };
  agentGatewayPackage = pkgs.callPackage ../pkgs/sinnix-agent-gateway/pkg.nix {
    sinnix-mcp = sinnixMcpPackage;
    sinnix-lib = externalPackages.sinnix-lib;
    sinnixd = sinnixdPackage;
  };

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

  externalPackages = rec {
    # bd needs the dolt binary on PATH for sql-server mode (per-project server,
    # auto-started on demand). Embedded mode serializes every invocation on a
    # process-exclusive lock — under multi-agent fanouts that convoys for
    # minutes, and it pays ~2.3s engine startup per call vs ~65ms as a server
    # client. Wrap rather than add dolt globally so every bd consumer (hooks,
    # devshells, agent lanes) gets server capability unconditionally.
    beads =
      let
        # No local patches. Upstream carries its own guard for the stale
        # issues.jsonl defect (a stale file re-imposed over newer Dolt rows
        # on every mutating command after a branch switch) -- the
        # GetStatistics emptiness guard in cmd/bd/auto_import_upgrade.go.
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
    # PYTHONPATH/PYTHONHOME/… unset, but does NOT cover polylogue-hook, which
    # ships as an unwrapped console_scripts entry point and runs from
    # arbitrary agent-devshell environments. Use symlink trees to expose only
    # the intended commands per package.
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

    sinnix-mcp = sinnixMcpPackage;
    sinnixd = sinnixdPackage;
    # The same tool without its test-suite check phase: environment builds
    # (dev shell, rebuild wrappers) need the binary, not the gate. The gate
    # stays on `sinnixd` for the suite check and the deployed service; a
    # worktree with red work-in-progress tests must still produce a usable
    # environment or continuation lanes can never start to fix it.
    sinnixd-tooling = sinnixdPackage.overridePythonAttrs (_: {
      doCheck = false;
    });
    sinnix-agent-gateway = agentGatewayPackage;
    tunnel-client = pkgs.callPackage ../pkgs/tunnel-client { };

    chatgpt-app = pkgs.callPackage ../pkgs/chatgpt-app { };

    sinnix-observe = pkgs.callPackage ../pkgs/sinnix-observe/pkg.nix {
      inherit defaultRuntimeInventoryJson;
    };

    sinnix-ops-reducer = pkgs.callPackage ../pkgs/sinnix-ops-reducer/pkg.nix {
      inherit sinnix-lib;
      kittyPackage = pkgs.kitty;
      ahaPackage = pkgs.aha;
    };

    # Shared Python library (importable, not a CLI): atomic state, ledgers,
    # locks, notify, systemd probes, spools. Python packages here depend on
    # it instead of carrying private copies of these helpers.
    sinnix-lib = pkgs.callPackage ../pkgs/sinnix-lib/pkg.nix { };

    # Shared pairwise/choice-set preference ranking engine (importable, not
    # a CLI): Plackett-Luce fit, stopping statistic, selection, draw
    # policies. scripts/sinnix-rank is its text frontend.
    sinnix-rank-core = pkgs.callPackage ../pkgs/sinnix-rank-core/pkg.nix { };

    # Steering CLI: source lives in the steering workspace (a non-flake
    # git+file input), packaging lives here — the same split as lynchpin's
    # python. Runtime deps mirror the frontmatter the script carried while
    # it lived under scripts/ (python3 claude-code libnotify).
    sinnix-steer = pkgs.writeShellApplication {
      name = "sinnix-steer";
      runtimeInputs = [
        pkgs.python3
        pkgs.claude-code
        pkgs.libnotify
      ];
      text = ''
        exec python3 ${inputs.steering}/sinnix-steer "$@"
      '';
      meta.description = "Steering store CLI — intentions, forecasts, activities, rituals";
    };

    sinnix-cockpit = pkgs.callPackage ../pkgs/sinnix-cockpit/pkg.nix { };

    sinnix-quota = pkgs.callPackage ../pkgs/sinnix-quota/pkg.nix { inherit sinnix-lib; };

    sinnix-deslop = pkgs.callPackage ../pkgs/sinnix-deslop/pkg.nix { };

    sinnix-capture = sinnixCaptureLib;

    sinnix-capture-a11y = pkgs.callPackage ../pkgs/sinnix-capture-a11y/pkg.nix {
      sinnix-capture-lib = sinnix-capture;
    };

    sinnix-audio-capture = pkgs.callPackage ../pkgs/sinnix-audio-capture/pkg.nix {
      sinnix-capture-lib = sinnix-capture;
    };

    # Prime's half of the phone's dual transport (docs/phone.md). Moved out
    # of scripts/ (sinnix-svvz) so it can depend on sinnix-capture's writer
    # instead of carrying a private stdlib-only port of it. steerPackage/
    # scorePackage replace the retired script frontmatter's `runtimeInputs:
    # coreutils @sinnix-steer @sinnix-score` -- a buildPythonApplication has
    # no writeShellApplication wrapper of its own to carry those, so pkg.nix
    # puts them on the built console_script's PATH directly.
    sinnix-phone-dispatcher = pkgs.callPackage ../pkgs/sinnix-phone-dispatcher/pkg.nix {
      sinnix-capture-lib = sinnix-capture;
      inherit sinnix-lib;
      steerPackage = sinnix-steer;
      scorePackage = discovered.registry.sinnix-score.package;
    };

    sinnix-capture-screen = pkgs.callPackage ../pkgs/capture-screen/pkg.nix { };

    # Xiaomi cloud health witness: pinned GPL-3 upstream client + our
    # orchestration entry, run under Bun (pkgs/sinnix-xiaomi-witness).
    sinnix-xiaomi-witness = pkgs.callPackage ../pkgs/sinnix-xiaomi-witness/pkg.nix { };

    # The Android capture app. `sinnix-phone-app` is the unsigned APK;
    # `sinnix-phone-app-install` signs it with the host-local keystore and
    # sideloads it over adb.
    sinnix-phone-app = phoneAppPackage;
    sinnix-phone-app-install = phoneAppPackage.install;

    sinnix-agent-environment-doc = pkgs.writeShellApplication {
      name = "sinnix-agent-environment-doc";
      runtimeInputs = [
        pkgs.bash
        pkgs.coreutils
        pkgs.findutils
        pkgs.gawk
        pkgs.jq
        pkgs.ripgrep
      ];
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
  packages = scriptPackages // {
    inherit (externalPackages) sinnix-agent-environment-doc;
  };
  inherit packageSet;
  inherit registry;
  list = lib.attrNames registry;
}
