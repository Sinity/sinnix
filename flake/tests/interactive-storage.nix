{ inputs, ... }:
let
  inherit (inputs.nixpkgs) lib;
in
{
  perSystem =
    { system, pkgs, ... }:
    let
      testLib = import ../test-lib.nix { inherit inputs lib; };
      cacheDir = "/run/sinnix-chrome-cache";
      evaluated = testLib.evalTestSpec system {
        name = "interactive-storage";
        modules = [
          testLib.mountTmpfsRoots
          testLib.baseTestConfig
          {
            sinnix.machine.isDesktop = true;
            # Exercise the real launcher and the flags given to nixpkgs'
            # Chrome override without rebuilding the browser for this check.
            nixpkgs.overlays = [
              (_final: prev: {
                google-chrome = lib.makeOverridable (
                  {
                    commandLineArgs ? "",
                  }:
                  prev.stdenvNoCC.mkDerivation {
                    pname = "google-chrome";
                    version = "fixture";
                    dontUnpack = true;
                    installPhase = ''
                      mkdir -p "$out/bin"
                      cat > "$out/bin/google-chrome-stable" <<'CHROME_STUB'
                      #!${prev.runtimeShell}
                      printf '%s\n' ${commandLineArgs} "$@" > "$CHROME_TEST_ARGS"
                      printf '%s\n' "$TMPDIR" > "$CHROME_TEST_TMPDIR"
                      CHROME_STUB
                      chmod +x "$out/bin/google-chrome-stable"
                      ln -s google-chrome-stable "$out/bin/google-chrome"
                    '';
                  }
                ) { };
              })
            ];
          }
        ];
        assertions =
          config:
          let
            mount = config.fileSystems.${cacheDir};
            hm = testLib.hmFor config;
          in
          [
            {
              assertion =
                config.fileSystems."/run/sinnix-chrome-tmp".fsType == "tmpfs"
                && lib.all (option: lib.elem option config.fileSystems."/run/sinnix-chrome-tmp".options) [
                  "size=512M"
                  "nr_inodes=4096"
                  "noswap"
                  "mode=0700"
                  "uid=${toString config.users.users.${config.sinnix.user.name}.uid}"
                ];
              message = "Chrome's temporary files must have a private, bounded, non-swappable RAM filesystem.";
            }
            {
              assertion = mount.fsType == "tmpfs" && mount.device == "tmpfs";
              message = "Chrome's HTTP cache must be on its own RAM filesystem.";
            }
            {
              assertion = lib.all (option: lib.elem option mount.options) [
                "size=256M"
                "nr_inodes=8192"
                "noswap"
                "mode=0700"
                "uid=${toString config.users.users.${config.sinnix.user.name}.uid}"
              ];
              message = "Chrome cache data, inodes and swap use must be bounded, with private user ownership.";
            }
            {
              assertion = lib.hasInfix "/bin/sinnix-chrome %U" hm.xdg.desktopEntries.google-chrome.exec;
              message = "The desktop entry must use the launcher tested by the cache fixture.";
            }
          ];
      };
      host = inputs.self.nixosConfigurations.sinnix-prime.config;
      writeback = host.systemd.services.sinnix-realm-writeback;
      writebackScript = pkgs.writeText "realm-writeback.sh" writeback.script;
      writebackUnit = host.systemd.units."sinnix-realm-writeback.service".text;
    in
    {
      checks.browser-ram-cache = testLib.mkHmRuntimeCheck system {
        name = "browser-ram-cache";
        inherit evaluated;
        homePackages = [
          "sinnix-chrome"
          "google-chrome"
        ];
        nativeBuildInputs = [ pkgs.python3 ];
        script = ''
          export CHROME_TEST_ARGS="$TMPDIR/chrome-args"
          export CHROME_TEST_TMPDIR="$TMPDIR/chrome-tmpdir"
          # Both direct aliases and the desktop launcher's scoped entry must
          # override an inherited slow-disk TMPDIR at the package boundary.
          for command in google-chrome google-chrome-stable sinnix-chrome; do
          TMPDIR=/slow-agent-scratch SINNIX_CHROME_SCOPED=1 "$command" 'https://example.invalid/a?b=c&d=e'
          python3 - <<'PY'
          import os
          from pathlib import Path
          args = Path(os.environ["CHROME_TEST_ARGS"]).read_text().splitlines()
          assert "--disk-cache-dir=${cacheDir}" in args, args
          assert "--disk-cache-size=134217728" in args, args
          assert "--user-data-dir=/home/${evaluated.config.sinnix.user.name}/.config/chrome-ws" in args, args
          assert args[-1] == "https://example.invalid/a?b=c&d=e", args
          assert Path(os.environ["CHROME_TEST_TMPDIR"]).read_text().strip() == "/run/sinnix-chrome-tmp"
          PY
          done
        '';
      };

      checks.realm-writeback =
        assert writeback.wantedBy == [ "multi-user.target" ];
        assert writeback.requires == [ "realm.mount" ];
        assert lib.all (unit: lib.elem unit writeback.after) [
          "realm.mount"
          "systemd-sysctl.service"
        ];
        assert writeback.serviceConfig.Type == "oneshot";
        assert writeback.serviceConfig.RemainAfterExit;
        # Force the rendered unit as well as the module declarations.
        assert lib.hasInfix "After=realm.mount systemd-sysctl.service" writebackUnit;
        pkgs.runCommand "realm-writeback-check" { nativeBuildInputs = [ pkgs.python3 ]; } ''
          python3 ${./realm-writeback.py} ${writebackScript}
          touch "$out"
        '';
    };
}
