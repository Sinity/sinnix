# Noctalia v5 plugin lint and bounded bridge contract.
{ inputs, ... }:
{
  perSystem =
    { system, ... }:
    let
      pkgs = inputs.nixpkgs.legacyPackages.${system};
      noctalia = pkgs.callPackage "${inputs.noctalia}/nix/package.nix" { };
      noctaliaThemeDefaultsMigration = noctalia.overrideAttrs (old: {
        # Match the deployed source, but opt into Meson's test targets only for
        # this check. The production package deliberately keeps tests disabled.
        patches = (old.patches or [ ]) ++ [
          ../../modules/features/desktop/noctalia-notification-prewarm.patch
          ../../modules/features/desktop/noctalia-automation-ipc.patch
          ../../modules/features/desktop/noctalia-memory-stats.patch
          ../../modules/features/desktop/noctalia-luau-ownership.patch
        ];
        postPatch = (old.postPatch or "") + ''
          patch -p1 < ${../../modules/features/desktop/noctalia-pipewire-reconnect.patch}
        '';
        mesonFlags = builtins.filter (flag: flag != "-Dtests=disabled") (old.mesonFlags or [ ]) ++ [
          "-Dtests=enabled"
        ];
        # Do not compile Noctalia's complete upstream suite: this target pulls
        # in the core library plus the one migration executable under test.
        buildPhase = ''
          runHook preBuild
              meson compile theme_defaults_migration_test
          runHook postBuild
        '';
        doCheck = true;
        checkPhase = ''
          runHook preCheck
              meson test --no-rebuild --print-errorlogs theme_defaults_migration
          runHook postCheck
        '';
        installPhase = ''
          mkdir -p "$out"
          touch "$out/passed"
        '';
        postFixup = "";
      });
    in
    {
      checks = {
        noctalia-theme-defaults-migration = noctaliaThemeDefaultsMigration;
        noctalia-luau-ownership =
          pkgs.runCommand "noctalia-luau-ownership-check"
            {
              nativeBuildInputs = [
                pkgs.stdenv.cc
                pkgs.patch
                pkgs.ripgrep
              ];
              buildInputs = [ pkgs.nlohmann_json ];
            }
            ''
              mkdir -p source/src/app source/src/util source/src/scripting source/tests "$out"
              cp ${inputs.noctalia}/meson.build source/
              cp ${inputs.noctalia}/src/app/application_ipc.cpp source/src/app/
              cp ${inputs.noctalia}/src/scripting/script_runtime.cpp source/src/scripting/
              patch -d source -p1 < ${../../modules/features/desktop/noctalia-memory-stats.patch}
              patch -d source -p1 < ${../../modules/features/desktop/noctalia-luau-ownership.patch}
              c++ -std=c++23 -UNDEBUG -DNOCTALIA_OWNERSHIP_FIXTURE -pthread \
                -fsanitize=address -fno-omit-frame-pointer -I source/src \
                source/tests/runtime_memory_test.cpp -o runtime-memory-test
              ./runtime-memory-test > "$out/ownership-fixture.json"
              mkdir -p baseline/scripting
              sed -e 's/static auto\* const registry = new RuntimeMemoryRegistry;/static RuntimeMemoryRegistry registry;/' \
                -e 's/return \*registry;/return registry;/' \
                source/src/scripting/runtime_memory.h > baseline/scripting/runtime_memory.h
              c++ -std=c++23 -UNDEBUG -pthread -fsanitize=address -fno-omit-frame-pointer \
                -I baseline source/tests/runtime_memory_test.cpp -o baseline-runtime-memory-test
              if ./baseline-runtime-memory-test --late-state > "$out/shutdown-baseline.log" 2>&1; then
                echo 'ordinary static registry unexpectedly survived late State destruction' >&2
                exit 1
              fi
              rg -q 'AddressSanitizer: heap-use-after-free' "$out/shutdown-baseline.log"
            '';
        noctalia-memory-stats =
          pkgs.runCommand "noctalia-memory-stats-check"
            {
              nativeBuildInputs = [
                pkgs.stdenv.cc
                pkgs.patch
              ];
              buildInputs = [
                pkgs.nlohmann_json
                pkgs.jemalloc
              ];
            }
            ''
              mkdir -p source/src/app source/src/util source/tests
              cp ${inputs.noctalia}/meson.build source/
              cp ${inputs.noctalia}/src/app/application_ipc.cpp source/src/app/
              patch -d source -p1 < ${../../modules/features/desktop/noctalia-memory-stats.patch}
              # Preserve the real allocation for jemalloc observation.
              c++ -std=c++23 -UNDEBUG -fno-builtin-malloc -fno-builtin-free \
                -DNOCTALIA_ALLOCATOR_REAL_TEST -I source/src \
                source/tests/allocator_stats_test.cpp -ljemalloc -o allocator-stats-test
              ./allocator-stats-test
              touch "$out"
            '';
        noctalia-hub-bridge =
          pkgs.runCommand "noctalia-hub-bridge-check"
            {
              nativeBuildInputs = [
                noctalia
                pkgs.bash
                pkgs.coreutils
                pkgs.gnugrep
                pkgs.gnused
                pkgs.luau
                pkgs.python3
              ];
            }
            ''
              NOCTALIA_HUB_PLUGIN=${../../dots/noctalia/plugins/sinnix-hub} \
              NOCTALIA_HUB_SERVER=${../../pkgs/sinnix-hub-server} \
              NOCTALIA_RUNTIME=${../../pkgs/sinnix-runtime} \
              NOCTALIA_HUB_CONTRACT=${../../flake/tests/noctalia-state-contract.py} \
              NOCTALIA_HUB_ORDERING=${./noctalia-hub-ordering.py} \
                ${pkgs.bash}/bin/bash ${../../flake/tests/noctalia-hub-bridge.sh}
              touch "$out"
            '';
        noctalia-bar-lint =
          pkgs.runCommand "noctalia-bar-lint-check"
            {
              nativeBuildInputs = [
                noctalia
                pkgs.bash
                pkgs.coreutils
                pkgs.luau
              ];
            }
            ''
              # Manifest/settings cross-check, then a real parse of every entry:
              # `noctalia plugins lint` does not compile Luau, so a syntax error
              # would otherwise surface only at live shell load.
              noctalia plugins lint ${../../dots/noctalia/plugins/sinnix-bar}
              for entry in ${../../dots/noctalia/plugins/sinnix-bar}/*.luau; do
                luau-compile --binary "$entry" > /dev/null
              done
              touch "$out"
            '';
        noctalia-config-validate =
          pkgs.runCommand "noctalia-config-validate-check"
            {
              nativeBuildInputs = [
                noctalia
                pkgs.bash
                pkgs.coreutils
              ];
            }
            ''
              ${pkgs.bash}/bin/bash ${../../flake/tests/noctalia-config.sh} ${../../dots/noctalia}
              touch "$out"
            '';
        noctalia-patches-apply =
          pkgs.runCommand "noctalia-patches-apply-check"
            {
              nativeBuildInputs = [
                pkgs.bash
                pkgs.coreutils
                pkgs.git
                pkgs.patch
                pkgs.ripgrep
              ];
            }
            ''
              ${pkgs.bash}/bin/bash ${../../flake/tests/noctalia-patches.sh} \
                ${inputs.noctalia.outPath} \
                ${../../modules/features/desktop/noctalia-automation-ipc.patch} \
                ${../../modules/features/desktop/noctalia-pipewire-reconnect.patch} \
                ${../../scripts/sinnix-wallpaper} \
                ${../../scripts/sinnix-wallpaper-timeofday} \
                ${../../flake/tests/noctalia-wallpaper-timeofday.sh} \
                ${../../modules/features/desktop/noctalia-memory-stats.patch} \
                ${../../modules/features/desktop/noctalia-luau-ownership.patch}
              touch "$out"
            '';
      };
    };
}
