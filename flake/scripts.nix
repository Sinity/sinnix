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
      # sinnix-phone-dispatcher moved out of scripts/ into a real Python
      # package (sinnix-svvz); scripts/sinnix-phone still names
      # @sinnix-phone-dispatcher in its own runtimeInputs and resolves here.
      sinnix-phone-dispatcher = externalPackages.sinnix-phone-dispatcher;
      sinnix-phone-keyguard = externalPackages.sinnix-phone-keyguard;
      # Sinnix's bd, not nixpkgs'. A script naming bare `beads` in its
      # frontmatter gets pkgs.beads (1.0.3), whose `export` has no -C flag --
      # which failed as a usage dump swallowed by `|| true`.
      beads = externalPackages.beads;
      # Native runtime and HTTP presentation are separate Python packages;
      # scripts resolve their entry points through this dependency map.
      sinnix-hub-server = externalPackages.sinnix-hub-server;
      sinnix-runtime = externalPackages.sinnix-runtime;
    };
  };
  discovered = discovery.discover (inputs.self + "/scripts");

  registry = discovered.registry // {
    sinnix-fs = {
      description = "Inspect, classify, catalog and maintain the filesystem";
      package = externalPackages.sinnix-fs;
      runtimeInputs = [ ];
      owner = "pkgs/sinnix-fs";
      docs = "docs/filesystem-index.md";
    };
    # The witness and its login helper are packaged entry points, so script
    # discovery cannot expose their existing operator commands by itself.
    sinnix-capture-xiaomi-cloud = {
      description = "Sync Xiaomi cloud band data";
      package = externalPackages.sinnix-capture-xiaomi-cloud;
      runtimeInputs = [ ];
      owner = "flake/scripts.nix";
      docs = "docs/phone.md";
    };
    sinnix-xiaomi-cloud-login = {
      description = "Authenticate the Xiaomi cloud band witness";
      package = externalPackages.sinnix-capture-xiaomi-cloud.overrideAttrs (old: {
        meta = old.meta // {
          mainProgram = "sinnix-xiaomi-cloud-login";
        };
      });
      runtimeInputs = [ ];
      owner = "flake/scripts.nix";
      docs = "docs/phone.md";
    };
  };
  scriptPackages = lib.mapAttrs (_: v: v.package) registry // {
    # Generated meta-CLI entry point over every packaged script above. Kept
    # in scriptPackages (not externalPackages) because it is derived
    # entirely from `registry`, not from an external flake input.
    sinnix = import ./cli-dispatcher.nix { inherit lib pkgs registry; };
  };
  mcpRegistry = import ./data/mcp-registry.nix { inherit lib; };
  agentProfiles = import ./data/agent-profiles.nix;
  agentEnvironmentSelections = [
    {
      name = "claude";
      client = "claude";
      selection = "default";
    }
    {
      name = "codex";
      client = "codex";
      selection = "default";
    }
    {
      name = "codex-local";
      client = "codex";
      selection = "full";
    }
    {
      name = "codex-deepseek";
      client = "codex";
      selection = "full";
    }
    {
      name = "gemini";
      client = "gemini";
      selection = "full";
    }
    {
      name = "antigravity";
      client = "antigravity";
      selection = "antigravity";
    }
    {
      name = "hermes";
      client = "hermes";
      selection = "evidence";
    }
  ]
  ++ lib.mapAttrsToList (name: profile: {
    name = "hermes-${name}";
    client = "hermes";
    selection = profile.mcpProfile or "evidence";
  }) agentProfiles.hermesProfiles;
  agentEnvironmentData = pkgs.writeText "sinnix-agent-environment-data.json" (
    builtins.toJSON {
      profiles = map (row: {
        inherit (row) name client;
        tiers = mcpRegistry.profileTiers.${row.selection};
        servers = lib.attrNames (mcpRegistry.selectClientServersForProfile row.selection row.client);
      }) agentEnvironmentSelections;
      servers = lib.mapAttrsToList (name: server: {
        inherit name;
        inherit (server) tier transport clients;
        command = server.command or null;
        url = server.url or null;
      }) mcpRegistry.registry;
    }
  );
  agentctlPackage = pkgs.callPackage ../pkgs/agentctl/pkg.nix {
    inherit (pkgs) pueue;
    sinnix-lib = externalPackages.sinnix-lib;
    beads = externalPackages.beads;
  };
  agentGatewayPackage = pkgs.callPackage ../pkgs/sinnix-agent-gateway/pkg.nix {
    sinnix-lib = externalPackages.sinnix-lib;
    sinnix-runtime = externalPackages.sinnix-runtime;
    agentctl = agentctlPackage;
  };
  mkSanitizedPythonWrapper =
    {
      name,
      target,
    }:
    pkgs.writeShellScriptBin name ''
      set -euo pipefail
      unset PYTHONPATH PYTHONHOME PYTHONBREAKPOINT PYTHONUSERBASE VIRTUAL_ENV
      unset _PYTHON_SYSCONFIGDATA_NAME _PYTHON_HOST_PLATFORM
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
    # recheck: when unblob's fs dependency supports Python 3.14 and setuptools 82.
    firmware-unblob =
      (pkgs.unblob.override {
        # recheck: when partclone builds against the pinned nilfs-utils headers.
        # Unblob uses partclone.info/restore, not its NILFS filesystem copier.
        partclone = pkgs.partclone.overrideAttrs (old: {
          configureFlags = lib.remove "--enable-nilfs2" old.configureFlags;
        });
        python3 = pkgs.python313.override {
          packageOverrides = final: prev: {
            fs = prev.fs.override { setuptools = final.setuptools_80; };
          };
        };
      }).overrideAttrs
        (old: {
          # recheck: when sandboxed Btrfs-stream replay can rename across directories.
          # The current kernel returns EXDEV under Landlock. Keep sandboxing enabled
          # and declare this format unverified rather than weakening containment.
          disabledTests = (old.disabledTests or [ ]) ++ [
            "test_all_handlers[filesystem.btrfs_stream]"
          ];
        });
    rea =
      (mkNodeCliPackage {
        pname = "rea";
        version = "6.2.0";
        src = ./npm/rea;
        packagePath = "rea-agents";
        entrypoint = "scripts/rea.mjs";
        npmDepsHash = "sha256-kfA9cOa54MH9CbLYJITTbs+ajjusCYPEs9yT6F9U38k=";
      }).overrideAttrs
        (old: {
          nativeBuildInputs = (old.nativeBuildInputs or [ ]) ++ [ pkgs.autoPatchelfHook ];
          buildInputs = (old.buildInputs or [ ]) ++ [ (lib.getLib pkgs.stdenv.cc.cc) ];
          postFixup = ''
            wrapProgram "$out/bin/rea" \
              --set GHIDRA_INSTALL_DIR ${pkgs.ghidra}/lib/ghidra \
              --set JAVA_HOME ${pkgs.openjdk21} \
              --set REA_BINWALK_COMMAND ${pkgs.binwalk}/bin/binwalk \
              --set REA_UNBLOB_COMMAND ${firmware-unblob}/bin/unblob \
              --set REA_FIRMWARE_PRLIMIT_COMMAND ${pkgs.util-linux}/bin/prlimit \
              --prefix PATH : ${
                lib.makeBinPath [
                  pkgs.python3
                  pkgs.openjdk21
                  pkgs.util-linux
                ]
              }
          '';
        });

    # bd needs the dolt binary on PATH for sql-server mode (per-project server,
    # auto-started on demand). Embedded mode serializes every invocation on a
    # process-exclusive lock — under multi-agent fanouts that convoys for
    # minutes, and it pays ~2.3s engine startup per call vs ~65ms as a server
    # client. Keep the wrapper's PATH injection so every bd consumer (hooks,
    # devshells, agent launcher profiles) gets server capability unconditionally, while
    # exposing the exact same Dolt package through passthru for the user PATH.
    beads =
      let
        doltPackage = pkgs.dolt;
        beadsBase =
          (pkgs.callPackage (inputs.beads + "/default.nix") {
            self = inputs.beads;
            buildGoModule = pkgs.buildGo126Module;
          }).overrideAttrs
            (old: {
              patches = (old.patches or [ ]) ++ [
                ../pkgs/beads/owner-contracts.patch
                ../pkgs/beads/standalone-context.patch
              ];
            });
        # bd's upstream --directory flag chooses the requested checkout only
        # while finding its configuration, then a redirect can send the
        # command back to the caller's cwd authority.  Normalize the flag at
        # the outer boundary instead: change cwd once and leave upstream no
        # ambiguous routing instruction.  This applies equally to -C.
        cwdWrapper = pkgs.writeShellScript "bd-cwd-wrapper" ''
          set -euo pipefail
          directory=""
          args=()
          parse_options=1
          while (( $# )); do
            if (( parse_options )) && [[ "$1" == "--" ]]; then
              args+=("$1")
              parse_options=0
              shift
              continue
            fi
            if (( parse_options )) && [[ "$1" == "--directory" || "$1" == "-C" ]]; then
              if (( $# < 2 )); then
                exec "$BD_UPSTREAM" "''${args[@]}" "$@"
              fi
              directory="$2"
              shift 2
              continue
            fi
            if (( parse_options )) && [[ "$1" == --directory=* ]]; then
              directory="''${1#--directory=}"
              shift
              continue
            fi
            if (( parse_options )) && [[ "$1" == -C?* ]]; then
              directory="''${1#-C}"
              shift
              continue
            fi
            args+=("$1")
            shift
          done
          if [[ -n "$directory" ]]; then
            cd -- "$directory"
          fi
          exec "$BD_UPSTREAM" "''${args[@]}"
        '';
      in
      pkgs.symlinkJoin {
        name = "beads-with-dolt";
        paths = [ beadsBase ];
        # Consumers that need the standalone Dolt CLI should use this exact
        # package, so its version cannot drift from the one wrapped into bd.
        passthru = {
          dolt = doltPackage;
          ownerContractCheck = beadsBase.overrideAttrs {
            doCheck = true;
            checkPhase = ''
              runHook preCheck
              BEADS_TEST_EMBEDDED_DOLT=1 go test -tags=gms_pure_go ./cmd/bd ./internal/beads ./internal/storage/issueops ./internal/storage/embeddeddolt -run 'OwnerContract|WrapWithSchemaVersion|OutputJSONWithPagination' -count=1 -timeout=2m
              go test -tags=gms_pure_go ./internal/httpapi ./issueops ./internal/storage/externaldeps -count=1 -timeout=2m
              runHook postCheck
            '';
          };
        };
        nativeBuildInputs = [ pkgs.makeWrapper ];
        postBuild = ''
          mv "$out/bin/bd" "$out/bin/.bd-upstream"
          makeWrapper ${cwdWrapper} "$out/bin/bd" \
            --set BD_UPSTREAM "$out/bin/.bd-upstream" \
            --prefix PATH : ${pkgs.lib.makeBinPath [ doltPackage ]}
        '';
      };

    lynchpin-python = mkSanitizedPythonWrapper {
      name = "lynchpin-python";
      target = "${inputs.lynchpin.packages.${pkgs.stdenv.hostPlatform.system}.api-python}/bin/python";
    };

    lynchpin-cli = mkSanitizedPythonWrappers {
      name = "lynchpin-cli";
      commands = {
        lynchpin-mcp = "${
          inputs.lynchpin.packages.${pkgs.stdenv.hostPlatform.system}.default
        }/bin/lynchpin-mcp";
      };
    };

    # Upstream sanitizes its Python entry points, including polylogue-hook.
    # Expose those wrappers directly and keep each package's command set narrow.
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

    mcp-github = mkNodeCliPackage {
      pname = "mcp-github";
      version = "2025.4.8";
      src = ./npm/github-mcp;
      packagePath = "@modelcontextprotocol/server-github";
      entrypoint = "dist/index.js";
      npmDepsHash = "sha256-Nc4KCBSqE+kDUBDkXjYVXybzysgpyaCjSNjrtZ04aJc=";
    };

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

    agentctl = agentctlPackage;
    sinnix-agent-gateway = agentGatewayPackage;
    tunnel-client = pkgs.callPackage ../pkgs/tunnel-client { };

    chatgpt-app = pkgs.callPackage ../pkgs/chatgpt-app { };

    machine-telemetry = pkgs.callPackage ../pkgs/machine-telemetry/pkg.nix {
      inherit sinnix-lib;
    };

    sinnix-hub-server = pkgs.callPackage ../pkgs/sinnix-hub-server/pkg.nix {
      inherit sinnix-lib sinnix-runtime;
    };

    # Shared Python library (importable, not a CLI): atomic state, ledgers,
    # locks, notify, systemd probes. Python packages here depend on
    # it instead of carrying private copies of these helpers.
    sinnix-lib = pkgs.callPackage ../pkgs/sinnix-lib/pkg.nix { };
    sinnix-fs = pkgs.callPackage ../pkgs/sinnix-fs/pkg.nix { inherit sinnix-lib; };
    sinnix-runtime = pkgs.callPackage ../pkgs/sinnix-runtime/pkg.nix { inherit sinnix-lib; };

    # Shared pairwise/choice-set preference ranking engine (importable, not
    # a CLI): Plackett-Luce fit, stopping statistic, selection, draw
    # policies. scripts/sinnix-rank is its text frontend.
    sinnix-rank-core = pkgs.callPackage ../pkgs/sinnix-rank-core/pkg.nix { inherit sinnix-lib; };

    sinnix-capture = sinnixCaptureLib;

    sinnix-capture-a11y = pkgs.callPackage ../pkgs/sinnix-capture-a11y/pkg.nix {
      sinnix-capture-lib = sinnix-capture;
    };

    sinnix-audio-capture = pkgs.callPackage ../pkgs/sinnix-audio-capture/pkg.nix {
      sinnix-capture-lib = sinnix-capture;
      inherit sinnix-lib;
    };

    # Prime's half of the phone's dual transport (docs/phone.md). Moved out
    # of scripts/ (sinnix-svvz) so it can depend on sinnix-capture's writer
    # instead of carrying a private stdlib-only port of it. scorePackage
    # replaces the retired script frontmatter's `@sinnix-score` -- a
    # buildPythonApplication has no writeShellApplication wrapper of its own
    # to carry it, so pkg.nix puts it on the built console_script's PATH.
    sinnix-phone-dispatcher = pkgs.callPackage ../pkgs/sinnix-phone-dispatcher/pkg.nix {
      sinnix-capture-lib = sinnix-capture;
      inherit sinnix-lib;
      scorePackage = discovered.registry.sinnix-score.package;
    };

    sinnix-capture-screen = pkgs.callPackage ../pkgs/sinnix-capture-screen/pkg.nix {
      inherit sinnix-lib;
    };

    # Xiaomi cloud health witness: pinned GPL-3 upstream client + our
    # orchestration entry, run under Bun (pkgs/sinnix-capture-xiaomi-cloud).
    sinnix-capture-xiaomi-cloud = pkgs.callPackage ../pkgs/sinnix-capture-xiaomi-cloud/pkg.nix { };

    # The Android capture app. `sinnix-phone-app` is the unsigned APK;
    # `sinnix-phone-app-install` signs it with the host-local keystore and
    # sideloads it over adb.
    sinnix-phone-keyguard = pkgs.callPackage ../pkgs/sinnix-phone-keyguard/pkg.nix {
      inherit (phoneAppPackage) jdk buildTools;
    };
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

    sinnix-agent-cli-locks = pkgs.writeShellApplication {
      name = "sinnix-agent-cli-locks";
      runtimeInputs = [
        pkgs.nodejs_22
        pkgs.python3
      ];
      text = ''
        exec python3 ${../pkgs/agent-cli-sources/update-locks.py} "$@"
      '';
      meta.description = "Render the npm locks for pinned agent CLI recovery tarballs";
    };
  };

  packageSet = scriptPackages // externalPackages;
in
{
  packages = scriptPackages // {
    inherit (externalPackages) sinnix-agent-environment-doc sinnix-agent-cli-locks;
  };
  inherit packageSet;
  inherit registry;
  list = lib.attrNames registry;
}
