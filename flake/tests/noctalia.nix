# Noctalia v5 plugin lint and bounded bridge contract.
{ inputs, ... }:
{
  perSystem =
    { system, ... }:
    let
      pkgs = inputs.nixpkgs.legacyPackages.${system};
      noctalia = inputs.noctalia.packages.${system}.default;
      noctaliaThemeDefaultsMigration = noctalia.overrideAttrs (old: {
        # Match the deployed source, but opt into Meson's test targets only for
        # this check. The production package deliberately keeps tests disabled.
        patches = (old.patches or [ ]) ++ [
          ../../modules/features/desktop/noctalia-notification-prewarm.patch
          ../../modules/features/desktop/noctalia-automation-ipc.patch
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
        noctalia-ops-bridge =
          pkgs.runCommand "noctalia-ops-bridge-check"
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
              NOCTALIA_OPS_PLUGIN=${../../dots/noctalia/plugins/sinnix-ops} \
              NOCTALIA_OPS_REDUCER=${../../pkgs/sinnix-ops-reducer} \
              NOCTALIA_OPS_OBSERVE=${../../pkgs/sinnix-observe} \
              NOCTALIA_OPS_CONTRACT=${../../flake/tests/noctalia-state-contract.py} \
                ${pkgs.bash}/bin/bash ${../../flake/tests/noctalia-ops-bridge.sh}
              touch "$out"
            '';
        noctalia-cockpit-lint =
          pkgs.runCommand "noctalia-cockpit-lint-check"
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
              noctalia plugins lint ${../../dots/noctalia/plugins/sinnix-cockpit}
              for entry in ${../../dots/noctalia/plugins/sinnix-cockpit}/*.luau; do
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
                ${../../flake/tests/noctalia-wallpaper-timeofday.sh}
              touch "$out"
            '';
      };
    };
}
