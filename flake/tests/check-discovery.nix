# Exercise the rendered commands: failed discovery must never mean zero green checks.
{ inputs, ... }:
{
  perSystem =
    { pkgs, system, ... }:
    let
      fakeNix = pkgs.writeShellScriptBin "nix" ''
        case "$1" in
          eval)
            echo eval >> "$EVALUATION_LOG"
            [ "''${DISCOVERY_FAIL:-0}" = 0 ] || exit 7
            printf '%s\n' "$DISCOVERY_JSON"
            ;;
          build)
            echo build >> "$BUILD_CALLS"
            shift
            printf '%s\n' "$@" >> "$BUILD_LOG"
            exit "''${BUILD_STATUS:-0}"
            ;;
          *) exit 64 ;;
        esac
      '';
      registry = import ../command-registry.nix {
        inherit inputs system;
        pkgs = pkgs // {
          nix = fakeNix;
        };
        sinnixScriptRegistry.packageSet = { };
      };
      commands = map (name: "${registry.mkAppCommand name registry.appCommands.${name}}/bin/${name}") [
        "check"
        "check-master"
        "check-heavy"
        "check-all"
      ];
      activationRegistry = import ../command-registry.nix {
        inherit inputs system;
        pkgs = pkgs // {
          systemd = pkgs.symlinkJoin {
            name = "fake-systemd-activation";
            paths = [
              (pkgs.writeShellScriptBin "systemd-run" ''
                if [ "''${ACTIVATION_BEFORE_REGISTER:-0}" = 1 ]; then
                  for arg in "$@"; do
                    case "$arg" in --property=ConditionPathExists=*) marker="''${arg#*=}"; marker="''${marker#*=}" ;; esac
                  done
                  if [ ! -e "$marker" ]; then
                    echo 'start condition missing before interruption' >&2
                    exit 88
                  fi
                  touch "$ACTIVATION_ENTERED"
                  while [ ! -e "$ACTIVATION_RELEASE" ]; do sleep 0.1; done
                  if [ ! -e "$marker" ]; then
                    echo skipped-registration >> "$ACTIVATION_LOG"
                    touch "$ACTIVATION_REGISTER_RESULT"
                    exit 143
                  fi
                fi
                printf '%s\n' "$*" >> "$ACTIVATION_LOG"
                if [ "''${ACTIVATION_HANG:-0}" = 1 ]; then
                  while [ ! -e "$ACTIVATION_RELEASE" ]; do sleep 0.1; done
                fi
                exit "$ACTIVATION_STATUS"
              '')
              (pkgs.writeShellScriptBin "systemctl" ''
                printf 'stop %s\n' "$*" >> "$ACTIVATION_LOG"
              '')
            ];
          };
          nix = pkgs.writeShellScriptBin "nix" ''
            echo unexpected-nix >> "$ACTIVATION_LOG"
            exit 99
          '';
        };
        sinnixScriptRegistry.packageSet = {
          sinnix-preflight = pkgs.writeShellScriptBin "sinnix-preflight" "exit 0";
          sinnix-sinex-cache-push = pkgs.writeShellScriptBin "sinnix-sinex-cache-push" ''
            echo cache-push >> "$ACTIVATION_LOG"
          '';
        };
      };
      fakeSudo = pkgs.writeShellScriptBin "sudo" ''exec "$@"'';
      activationExecutables = builtins.mapAttrs (
        name: package: "${package}/bin/${name}"
      ) activationRegistry.activationPackages;
      activationCases =
        pkgs.lib.concatMapStringsSep "\n"
          (
            name:
            let
              expectedArgv =
                {
                  switch = "nh os switch";
                  boot = "nh os boot";
                  test-system = "nh os test";
                  test-vm = "nixos-rebuild build-vm";
                }
                .${name};
            in
            "check_activation ${pkgs.lib.escapeShellArg name} ${
              pkgs.lib.escapeShellArg activationExecutables.${name}
            } ${pkgs.lib.escapeShellArg expectedArgv}"
          )
          [
            "switch"
            "boot"
            "test-system"
            "test-vm"
          ];
    in
    {
      checks.check-discovery = pkgs.runCommand "check-discovery" { } ''
        export SINNIX_FLAKE_DIR="$TMPDIR" BUILD_LOG="$TMPDIR/builds"
        export BUILD_CALLS="$TMPDIR/build-calls" EVALUATION_LOG="$TMPDIR/evaluations"
        good='{"one":"/nix/store/aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa-one.drv","two":"/nix/store/bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb-two.drv"}'
        unset AGENTCTL_PRINCIPAL AGENTCTL_OPERATION
        for command in ${pkgs.lib.escapeShellArgs commands}; do
          for malformed in '[]' '{}' 'null' 'invalid' '[1]' '[""]' '{"one":1}' '{"one":"relative.drv"}' '{"one":"/nix/store/value"}'; do
            : > "$BUILD_LOG"
            if DISCOVERY_JSON="$malformed" "$command"; then
              echo "invalid discovery succeeded: $malformed" >&2
              exit 1
            fi
            test ! -s "$BUILD_LOG"
          done
          : > "$BUILD_LOG"
          if DISCOVERY_FAIL=1 DISCOVERY_JSON="$good" "$command"; then
            echo "evaluation failure succeeded" >&2
            exit 1
          fi
          test ! -s "$BUILD_LOG"
          : > "$BUILD_LOG"
          : > "$BUILD_CALLS"
          : > "$EVALUATION_LOG"
          DISCOVERY_JSON="$good" "$command"
          test "$(wc -l < "$BUILD_CALLS")" = 1
          expected_evaluations=1
          case "$command" in */check-all) expected_evaluations=2 ;; esac
          test "$(wc -l < "$EVALUATION_LOG")" = "$expected_evaluations"
          grep -Fxq '/nix/store/aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa-one.drv^*' "$BUILD_LOG"
          grep -Fxq '/nix/store/bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb-two.drv^*' "$BUILD_LOG"
          if BUILD_STATUS=9 DISCOVERY_JSON="$good" "$command"; then
            echo "build failure succeeded" >&2
            exit 1
          fi
        done
        : > "$BUILD_LOG"
        DISCOVERY_JSON="$good" ${builtins.head commands} --no-build
        test ! -s "$BUILD_LOG"
        export SUDO_HOME="$TMPDIR" ACTIVATION_LOG="$TMPDIR/activation"
        ${pkgs.git}/bin/git init -q --bare "$TMPDIR/remote.git"
        ${pkgs.git}/bin/git init -q -b master "$TMPDIR/source"
        printf '{ }\n' > "$TMPDIR/source/flake.nix"
        ${pkgs.git}/bin/git -C "$TMPDIR/source" add flake.nix
        ${pkgs.git}/bin/git -C "$TMPDIR/source" -c user.name=Fixture -c user.email=fixture@example.test commit -qm initial
        ${pkgs.git}/bin/git -C "$TMPDIR/source" remote add origin "$TMPDIR/remote.git"
        ${pkgs.git}/bin/git -C "$TMPDIR/source" push -q -u origin master
        export SINNIX_FLAKE_DIR="$TMPDIR/source"
        printf '{ }\n' > "$TMPDIR/secret-declarations.nix"
        export SINNIX_SECRET_DECLARATIONS="$TMPDIR/secret-declarations.nix"
        export PATH="${fakeSudo}/bin:$PATH"
        check_activation() {
          name="$1"
          command="$2"
          expected_argv="$3"

          : > "$ACTIVATION_LOG"
          status=0
          AGENTCTL_PRINCIPAL=agent-control "$command" || status=$?
          test "$status" = 64
          test ! -s "$ACTIVATION_LOG"

          status=0
          SINNIX_SECRET_DECLARATIONS="$TMPDIR/missing-secret-declarations.nix" "$command" || status=$?
          test "$status" = 66
          test ! -s "$ACTIVATION_LOG"

          for expected in 7 130; do
            : > "$ACTIVATION_LOG"
            status=0
            SINNIX_SINEX_OVERRIDE=/tmp/sinex ACTIVATION_STATUS="$expected" "$command" || status=$?
            test "$status" = "$expected"
            expected_lines=1
            if [ "$name" = switch ]; then expected_lines=2; fi
            test "$(wc -l < "$ACTIVATION_LOG")" = "$expected_lines"
            grep -Fq "$expected_argv" "$ACTIVATION_LOG"
            grep -Fq -- '--override-input sinex /tmp/sinex' "$ACTIVATION_LOG"
            grep -Fq -- '--slice=nix-build.slice' "$ACTIVATION_LOG"
            if grep -q 'unexpected-nix\|cache-push' "$ACTIVATION_LOG"; then
              echo "$name failure attempted another execution route" >&2
              exit 1
            fi
          done
          : > "$ACTIVATION_LOG"
          ACTIVATION_STATUS=7 "$command" || test "$?" = 7
          if grep -Eq -- '--max-jobs|--cores|eval-cache = false' "$ACTIVATION_LOG"; then
            echo "$name overrode native Nix defaults" >&2
            exit 1
          fi
          : > "$ACTIVATION_LOG"
          SINNIX_REBUILD_MAX_JOBS=1 SINNIX_REBUILD_CORES=3 NIX_CONFIG="eval-cache = true" ACTIVATION_STATUS=7 "$command" || test "$?" = 7
          grep -Fq -- '--max-jobs 1 --cores 3' "$ACTIVATION_LOG"
          grep -Fq -- '--setenv=NIX_CONFIG=eval-cache = true' "$ACTIVATION_LOG"
        }
        ${activationCases}
        printf 'dirty\n' > "$TMPDIR/source/untracked"
        : > "$ACTIVATION_LOG"
        status=0
        ACTIVATION_STATUS=0 "${activationExecutables.switch}" || status=$?
        test "$status" = 64
        test ! -s "$ACTIVATION_LOG"
        SINNIX_ALLOW_DIRTY=1 ACTIVATION_STATUS=7 "${activationExecutables.switch}" || test "$?" = 7
        ${pkgs.coreutils}/bin/rm "$TMPDIR/source/untracked"
        ${pkgs.git}/bin/git -C "$TMPDIR/source" -c user.name=Fixture -c user.email=fixture@example.test commit -q --allow-empty -m newer
        ${pkgs.git}/bin/git -C "$TMPDIR/source" push -q origin master
        ${pkgs.git}/bin/git -C "$TMPDIR/source" reset -q --hard HEAD~1
        : > "$ACTIVATION_LOG"
        status=0
        ACTIVATION_STATUS=0 "${activationExecutables.switch}" || status=$?
        test "$status" = 64
        test ! -s "$ACTIVATION_LOG"
        ${pkgs.git}/bin/git -C "$TMPDIR/source" reset -q --hard origin/master
        : > "$ACTIVATION_LOG"
        source_revision="$(${pkgs.git}/bin/git -C "$TMPDIR/source" rev-parse HEAD)"
        SINNIX_FLAKE_DIR= NH_FLAKE="$TMPDIR/other" SINNIX_DEV_SHELL_REV="$source_revision" SINNIX_DEV_SHELL_FLAKE="$TMPDIR/source" SINNIX_DEV_SHELL_SOURCE="$TMPDIR/source" ACTIVATION_STATUS=7 "${activationExecutables.switch}" || test "$?" = 7
        grep -Fq "$TMPDIR/source#sinnix-prime" "$ACTIVATION_LOG"
        ${pkgs.git}/bin/git clone -q "$TMPDIR/source" "$TMPDIR/other"
        for caller_revision in same ahead; do
          shell_checkout="$TMPDIR/other"
          if [ "$caller_revision" = ahead ]; then
            ${pkgs.git}/bin/git -C "$TMPDIR/other" -c user.name=Fixture -c user.email=fixture@example.test commit -q --allow-empty -m caller-ahead
            shell_checkout=
          fi
          : > "$ACTIVATION_LOG"
          SINNIX_FLAKE_DIR= NH_FLAKE="$TMPDIR/other" SINNIX_DEV_SHELL_REV="$source_revision" \
            SINNIX_DEV_SHELL_FLAKE="$shell_checkout" SINNIX_DEV_SHELL_SOURCE="$TMPDIR/source" \
            ACTIVATION_STATUS=7 "${activationExecutables.switch}" || test "$?" = 7
          grep -Fq "$TMPDIR/source#sinnix-prime" "$ACTIVATION_LOG"
          if grep -Fq "$TMPDIR/other#sinnix-prime" "$ACTIVATION_LOG"; then
            echo 'devshell rebuilt the caller checkout' >&2
            exit 1
          fi
        done
        : > "$ACTIVATION_LOG"
        status=0
        SINNIX_DEV_SHELL_REV=0000000000000000000000000000000000000000 SINNIX_DEV_SHELL_FLAKE="$TMPDIR/source" ACTIVATION_STATUS=0 "${activationExecutables.switch}" || status=$?
        test "$status" = 64
        test ! -s "$ACTIVATION_LOG"
        status=0
        SINNIX_DEV_SHELL_REV=0000000000000000000000000000000000000000 SINNIX_DEV_SHELL_FLAKE= ACTIVATION_STATUS=0 "${activationExecutables.switch}" || status=$?
        test "$status" = 64
        test ! -s "$ACTIVATION_LOG"
        : > "$ACTIVATION_LOG"
        ACTIVATION_RELEASE="$TMPDIR/release" ACTIVATION_HANG=1 ACTIVATION_STATUS=0 "${activationExecutables.switch}" &
        wrapper=$!
        while [ ! -s "$ACTIVATION_LOG" ]; do sleep 0.1; done
        kill -TERM "$wrapper"
        status=0
        wait "$wrapper" || status=$?
        test "$status" = 143
        grep -Eq '^stop --user stop sinnix-switch-[0-9]+.service$' "$ACTIVATION_LOG"
        touch "$TMPDIR/release"
        : > "$ACTIVATION_LOG"
        ACTIVATION_BEFORE_REGISTER=1 ACTIVATION_ENTERED="$TMPDIR/entered" \
          ACTIVATION_RELEASE="$TMPDIR/register-release" ACTIVATION_REGISTER_RESULT="$TMPDIR/register-result" ACTIVATION_STATUS=0 \
          "${activationExecutables.switch}" &
        wrapper=$!
        while [ ! -e "$TMPDIR/entered" ]; do sleep 0.1; done
        kill -TERM "$wrapper"
        status=0
        wait "$wrapper" || status=$?
        test "$status" = 143
        touch "$TMPDIR/register-release"
        while [ ! -e "$TMPDIR/register-result" ]; do sleep 0.1; done
        grep -Fq skipped-registration "$ACTIVATION_LOG"
        if grep -Fq 'nh os switch' "$ACTIVATION_LOG"; then
          echo 'rebuild registered after wrapper exit' >&2
          exit 1
        fi
        test -x "${activationExecutables.test-system}"
        test ! -e "${activationRegistry.activationPackages.test-system}/bin/test"

        : > "$ACTIVATION_LOG"
        ACTIVATION_STATUS=0 "${activationExecutables.switch}"
        test "$(wc -l < "$ACTIVATION_LOG")" = 2
        grep -Fq 'cache-push' "$ACTIVATION_LOG"

        : > "$ACTIVATION_LOG"
        ACTIVATION_STATUS=0 "${activationExecutables.test-vm}"
        test "$(wc -l < "$ACTIVATION_LOG")" = 1
        grep -Fq 'nixos-rebuild build-vm' "$ACTIVATION_LOG"
        if grep -q 'run-sinnix-prime-vm' "$ACTIVATION_LOG"; then
          echo 'test-vm launched a VM instead of stopping after the build' >&2
          exit 1
        fi
        touch "$out"
      '';
    };
}
