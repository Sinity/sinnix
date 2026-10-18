# Full suites depend on the exact deployed runtime outputs. Test sources and
# owner-contract validation never become inputs of those runtime packages.
{ inputs, ... }:
{
  perSystem =
    {
      system,
      pkgs,
      sinnixScriptRegistry,
      ...
    }:
    let
      # The phone runtime's steering dependency carries unfree claude-code.
      # Scope that permission to its existing package and suite.
      unfreePkgs = import inputs.nixpkgs {
        inherit system;
        config.allowUnfree = true;
      };
      scriptRegistryUnfree = import ../scripts.nix {
        inherit inputs;
        pkgs = unfreePkgs;
      };
      lib = pkgs.lib;
      pythonSuite =
        {
          name,
          package ? sinnixScriptRegistry.packageSet.${name},
          extraInputs ? [ ],
          beforeTests ? "",
          pytestArgs ? "",
          testSource ? null,
        }:
        let
          module = builtins.replaceStrings [ "-" ] [ "_" ] name;
          selectedTests =
            if testSource != null then
              testSource
            else
              lib.sources.sourceByRegex (../../pkgs + "/${name}") [
                "tests"
                "tests/.*"
                "test_.*[.]py"
                "conftest[.]py"
                "pyproject[.]toml"
                "fixtures"
                "fixtures/.*"
                "generate_.*[.]py"
              ];
          python = pkgs.python3.withPackages (ps: [
            package
            ps.pytest
            ps.pytest-timeout
          ]);
        in
        pkgs.runCommand "${name}-suite"
          {
            nativeBuildInputs = [
              python
              package
            ]
            ++ extraInputs;
            RUNTIME_PACKAGE = package;
            RUNTIME_MODULE = module;
          }
          ''
            cp -R ${selectedTests} source
            chmod -R u+w source
            cd source
            ln -s ${package}/${pkgs.python3.sitePackages}/${module} ${module}
            python -c 'import importlib, os; from pathlib import Path; module = importlib.import_module(os.environ["RUNTIME_MODULE"]); assert Path(module.__file__).resolve().is_relative_to(Path(os.environ["RUNTIME_PACKAGE"]))'
            ${beforeTests}
            cp ${./python-runtime-imports.py} runtime_import_contract.py
            python -m pytest -q -p runtime_import_contract ${pytestArgs}
            mkdir "$out"
            cp runtime-import-before.json runtime-import-after.json "$out/"
            printf '%s\n' "$RUNTIME_PACKAGE" > "$out/runtime"
          '';
      polylogueContracts = lib.sources.sourceByRegex inputs.polylogue [
        "polylogue"
        "polylogue/(operations|core|archive)"
        "polylogue/archive/query"
        "polylogue/operations/session_contracts[.]py"
        "polylogue/core/enums[.]py"
        "polylogue/archive/query/spec[.]py"
      ];
      lynchpinContract = builtins.path {
        path = "${inputs.lynchpin}/lynchpin/mcp/project_contracts.py";
        name = "lynchpin-project-contracts.py";
      };
      # Exercise the real registry entries and renderer without realizing
      # unrelated commands (including their unfree runtime dependencies).
      xiaomiDispatcher = import ../cli-dispatcher.nix {
        inherit pkgs;
        lib = pkgs.lib;
        registry = pkgs.lib.getAttrs [
          "sinnix-xiaomi-witness"
          "sinnix-xiaomi-witness-login"
        ] sinnixScriptRegistry.registry;
      };
    in
    {
      checks = {
        beads-owner-contract = sinnixScriptRegistry.packageSet.beads.ownerContractCheck;
        # Provably fails when: is_near_duplicate's threshold boundary stops
        # being inclusive. Verified by flipping `<= threshold` to `< threshold`
        # in hashing.py -- caught by
        # test_is_near_duplicate_threshold_is_inclusive_boundary (1 failed,
        # 53 passed); reverted after confirming red.
        sinnix-capture-screen-suite = sinnixScriptRegistry.packageSet.sinnix-capture-screen;

        # Provably fails when: the "5m"/"2h" duration-unit table drifts from
        # real seconds. Verified by changing the minute multiplier 60.0 ->
        # 61.0 in pause.py -- caught by test_parse_duration[5m-300.0] (1
        # failed, 60 passed); reverted after confirming red.
        sinnix-audio-capture-suite = sinnixScriptRegistry.packageSet.sinnix-audio-capture;

        # Provably fails when: the debounce gate's suppress condition
        # inverts. Verified by flipping `< self._min_interval` to `>` in
        # debounce.py -- caught by three tests (two unit, one daemon
        # integration: 3 failed, 16 passed); reverted after confirming red.
        sinnix-capture-a11y-suite = pythonSuite { name = "sinnix-capture-a11y"; };

        # Provably fails when: /today stops distinguishing open from closed
        # commitments. Verified by changing store.py's open_commitments query
        # from `status = 'open'` to `status = 'done'` -- caught by
        # test_today_renders_open_commitment_with_forecast (1 failed, 3
        # passed); reverted after confirming red. (Note: the sibling
        # /calibration "actual rate" assertion in test_app.py is vacuous --
        # its "100%" substring check also matches the page's unrelated
        # `table { width: 100%; }` CSS rule -- a pre-existing test-quality
        # defect, out of scope here since it isn't this task's reachability
        # question.)
        sinnix-cockpit-suite = sinnixScriptRegistry.packageSet.sinnix-cockpit;

        # Provably fails when: STRIP_SENTENCE rules stop dropping the
        # sentence they match (keep everything else). Verified by inverting
        # the `not pattern.search(s)` keep-predicate in filter.py -- caught
        # by four tests including the STRIP_SENTENCE case (4 failed, 4
        # passed); reverted after confirming red.
        sinnix-deslop-suite = sinnixScriptRegistry.packageSet.sinnix-deslop;

        # Provably fails when: send_token dedup stops recognizing a token
        # it's already seen. Verified by making seen_token() always return
        # False in execute.py -- caught by
        # test_second_execution_with_same_token_is_a_noop_duplicate (1
        # failed, 46 passed); reverted after confirming red.
        #
        # Built with a locally-configured nixpkgs instance: this package's
        # steerPackage dependency (sinnix-steer) carries pkgs.claude-code on
        # its runtimeInputs, and claude-code is unfree -- plain legacyPackages
        # (the unconfigured instance every other check here uses) refuses to
        # even evaluate its drvPath. Same pattern as
        # flake/overlay/package/local-ai.nix's aiPkgs, scoped to this one
        # check rather than flipping allowUnfree tree-wide.
        sinnix-phone-dispatcher-suite = pythonSuite {
          name = "sinnix-phone-dispatcher";
          package = scriptRegistryUnfree.packageSet.sinnix-phone-dispatcher;
        };

        # Provably fails when: the project-path sandbox stops rejecting a
        # path that resolves outside the project root (e.g. via a symlink).
        # Verified by neutering `_safe_path`'s escape check (`root not in
        # resolved.parents` -> `False`) in projects.py -- caught by
        # test_project_tree_and_read_reject_symlink_escape ("DID NOT RAISE
        # ProjectError"; 1 failed, 23 passed); reverted after confirming red.
        sinnix-agent-gateway-suite = pythonSuite {
          name = "sinnix-agent-gateway";
          extraInputs = [
            pkgs.fd
            pkgs.file
            pkgs.git
            pkgs.ripgrep
          ];
          beforeTests = ''
            export SINNIX_CAPTURE_TEST_EXECUTABLE="${sinnixScriptRegistry.packageSet.sinnix-capture}/bin/sinnix-capture"
            export SINNIX_GATEWAY_TEST_EXECUTABLE="${sinnixScriptRegistry.packageSet.sinnix-agent-gateway}/bin/sinnix-agent-gateway"
            python generate_owner_inputs.py --polylogue ${polylogueContracts} --lynchpin ${lynchpinContract} --check
            ${sinnixScriptRegistry.packageSet.beads}/bin/bd owner schema --json > "$TMPDIR/beads-owner-schema.json"
            python generate_beads_inputs.py "$TMPDIR/beads-owner-schema.json" --check
          '';
        };
        machine-telemetry-suite = pythonSuite {
          name = "machine-telemetry";
          testSource = lib.fileset.toSource {
            root = ../../pkgs/machine-telemetry;
            fileset = lib.fileset.unions [
              ../../pkgs/machine-telemetry/tests/test_collector_process_memory.py
              ../../pkgs/machine-telemetry/tests/test_rotation.py
            ];
          };
          extraInputs = [
            pkgs.coreutils
            pkgs.zstd
          ];
          pytestArgs = "tests/test_collector_process_memory.py tests/test_rotation.py";
          beforeTests = ''
            export SINNIX_SQLITE_BACKUP="${sinnixScriptRegistry.packageSet.sinnix-sqlite-backup}/bin/sinnix-sqlite-backup"
          '';
        };
        sqlite-backup-package = sinnixScriptRegistry.packageSet.sinnix-sqlite-backup;
        sqlite-backup-suite =
          pkgs.runCommand "sqlite-backup-suite"
            {
              nativeBuildInputs = [
                (pkgs.python3.withPackages (ps: [ ps.pytest ]))
                pkgs.zstd
              ];
              SINNIX_SQLITE_BACKUP = "${sinnixScriptRegistry.packageSet.sinnix-sqlite-backup}/bin/sinnix-sqlite-backup";
            }
            ''
              cp ${../../pkgs/machine-telemetry/tests/test_backup.py} test_backup.py
              # Inspect the exact wrapper's declared Python payload for the one
              # in-process cancellation test. All CLI tests execute the wrapper.
              export SINNIX_SQLITE_BACKUP_MODULE="$(python - <<'PY'
              import os, shlex
              from pathlib import Path
              lines = Path(os.environ['SINNIX_SQLITE_BACKUP']).read_text().splitlines()
              commands = [shlex.split(line) for line in lines if line.startswith('exec /nix/store/')]
              assert len(commands) == 1
              payload = Path(commands[0][1])
              assert payload.is_file() and payload.read_text().startswith('#!')
              print(payload)
              PY
              )"
              python -m pytest -q test_backup.py
              touch "$out"
            '';

        # Shared-library verification is explicit, independent of consumers.
        #
        # Provably fails when: sd_notify stops translating a leading "@" into
        # the abstract namespace. Verified by deleting the
        # `address.startswith("@")` branch in systemd.py -- caught by
        # test_sd_notify_reaches_an_abstract_namespace_socket ("TimeoutError:
        # timed out"; 1 failed, 30 passed); reverted after confirming red.
        # Also fails when the subprocess wrapper stops swallowing
        # TimeoutExpired: verified by dropping that except clause in
        # process.py -- caught by test_run_returns_a_result_when_the_command_hangs
        # (subprocess.TimeoutExpired; 1 failed, 30 passed); reverted after
        # confirming red.
        sinnix-lib-suite = pythonSuite { name = "sinnix-lib"; };
        xiaomi-witness-cli = sinnixScriptRegistry.packageSet.sinnix-xiaomi-witness;
        xiaomi-witness-dispatch =
          pkgs.runCommand "xiaomi-witness-dispatch-check"
            {
              nativeBuildInputs = [ pkgs.gnugrep ];
              SINNIX_CLI = "${xiaomiDispatcher}/bin/sinnix";
              LOGIN_APP = pkgs.lib.getExe sinnixScriptRegistry.packageSet.sinnix-xiaomi-witness-login;
            }
            ''
                export XIAOMI_WITNESS_STATE="$TMPDIR/uncreated-state"
                export XIAOMI_WITNESS_LANE="$TMPDIR/uncreated-lane"
                for command in xiaomi-witness xiaomi-witness-login; do
                  "$SINNIX_CLI" "$command" --help > help.txt
                  grep -q '^Usage:' help.txt
                done
                "$LOGIN_APP" --help > login-app-help.txt
              grep -q '^Usage: sinnix xiaomi-witness-login' login-app-help.txt
              test ! -e "$XIAOMI_WITNESS_STATE"
                test ! -e "$XIAOMI_WITNESS_LANE"
                touch "$out"
            '';

        # The selection capture both Wayland lanes run. Provably fails when:
        # the MIME preference order is permuted (an adjacent swap fails
        # test_preference_order_holds_for_every_adjacent_pair), or the blob
        # shard prefix length changes (fails
        # test_binary_selection_lands_in_a_two_character_shard and the
        # store-once case). Both Wayland lanes use this exact runtime output.
        sinnix-capture-suite = pythonSuite { name = "sinnix-capture"; };

        # Provably fails when: the launch input stops carrying the descriptor's
        # argv, pool, label or artifact paths, or the pueue adapter misreads
        # the daemon's JSON. The suite drives a private pueued end to end.
        agentctl-suite = pythonSuite {
          name = "agentctl";
          extraInputs = builtins.filter (
            p:
            lib.elem (p.pname or (lib.getName p)) [
              "git"
              "beads"
              "beads-with-dolt"
              "worktrunk"
              "pueue"
            ]
          ) sinnixScriptRegistry.packageSet.agentctl.runtimeDependencies;
        };
      };
    };
}
