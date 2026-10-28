# Polylogue service module evaluation checks.
#
# The live wrapper is the daemon's command and the browser host, so both must
# name the same archive; the host manifest must allow the ID Chrome derives
# from the extension directory.
#
# Provably fails when: the unit's ExecStart or the host manifest stops going
# through the polylogue-live wrapper, or the extension ID derivation changes
# (checked against an ID Chrome assigned to a known path).
{ inputs, ... }:
let
  inherit (inputs.nixpkgs) lib;
in
{
  perSystem =
    { system, ... }:
    let
      pkgs = inputs.nixpkgs.legacyPackages.${system};
      overlayLib = import ../../modules/lib/overlay-helpers.nix { inherit lib; };
      polyloguePackage =
        (import ../overlay/package/polylogue.nix { inherit inputs overlayLib; } pkgs pkgs).polylogue;
      testLib = import ../test-lib.nix { inherit inputs lib; };
      inherit (testLib)
        evalTestSpec
        hmFor
        mkServiceTest
        ;

      sentinelDataDir = "/tmp/sinnix-polylogue-service-sentinel";
      liveRoot = "/tmp/sinnix-polylogue-live-sentinel";
      liveSpec = mkServiceTest {
        name = "polylogue-live";
        service = "polylogue";
        extraModules = [
          (_: {
            sinnix.services.polylogue.dataDir = sentinelDataDir;
            sinnix.services.polylogue.liveRoot = liveRoot;
            sinnix.features.desktop.browser.enable = true;
          })
        ];
        assertions = _config: [ ];
      };
      liveEvaluated = evalTestSpec system liveSpec;
      hm = hmFor liveEvaluated.config;
      liveService = hm.systemd.user.services.polylogue-live;
      hostManifest =
        hm.home.file.".config/chrome-ws/NativeMessagingHosts/com.polylogue.browser_capture.json".text;
      polylogueTmpfiles = liveEvaluated.config.systemd.tmpfiles.rules;
      archiveInventory = liveEvaluated.config.sinnix.runtime.inventory.polylogue;
    in
    {
      checks = {
        polylogue-live =
          pkgs.runCommand "sinnix-polylogue-live-check"
            {
              nativeBuildInputs = [ pkgs.jq ];
              execStart = liveService.Service.ExecStart;
              wantedBy = builtins.toJSON liveService.Install.WantedBy;
              servicePolicy = builtins.toJSON liveService.Service;
              inherit hostManifest liveRoot;
            }
            ''
              set -eu
              chrome_id() { printf %s "$1" | sha256sum | cut -c1-32 | tr 0-9a-f a-p; }
              # Chrome assigned this ID to an unpacked extension at this path.
              test "$(chrome_id /realm/worktree/polylogue-installed-candidate-d97162b/browser-extension)" \
                = pllhcjjmdhchcbobnkdegdnjhkciojkp
              id="$(chrome_id "$liveRoot/extension")"
              wrapper="''${execStart% daemon}"
              test "$execStart" = "$wrapper daemon"
              case "$wrapper" in */bin/polylogue-live) ;; *) exit 1 ;; esac
              jq -e 'index("default.target") != null' <<<"$wantedBy" >/dev/null
              jq -e '
                .Slice == "background.slice" and .IOWeight == 20 and
                .Nice == 10 and .IOSchedulingPriority == 7 and
                .MemoryHigh == "6G" and .MemoryMax == "9G" and
                .MemorySwapMax == "2G"
              ' <<<"$servicePolicy" >/dev/null
              jq -e --arg wrapper "$wrapper" --arg id "$id" '
                .path == $wrapper and
                .allowed_origins == ["chrome-extension://\($id)/"]
              ' <<<"$hostManifest" >/dev/null
              touch "$out"
            '';
        polylogue-archive-root =
          pkgs.runCommand "sinnix-polylogue-archive-root-check"
            {
              inherit sentinelDataDir;
              nativeBuildInputs = [ pkgs.jq ];
              actualTmpfiles = builtins.toJSON polylogueTmpfiles;
            }
            ''
              jq -e --arg root "$sentinelDataDir" '
                index("d \($root)/inbox 0700 sinity users -") != null and
                (map(select(startswith("L+ \($root)/inbox/"))) | length) == 0
              ' <<<"$actualTmpfiles" >/dev/null
              touch "$out"
            '';
        # Provably fails when: width_within / memory_bounded_worker_cap restore
        # max(1) (46 MiB slot-531 admits one worker), or either pytest_slot
        # launch path Popen's before a typed resource-not-ready deferral.
        polylogue-pytest-admission =
          pkgs.runCommand "sinnix-polylogue-pytest-admission-check"
            {
              nativeBuildInputs = [
                (polyloguePackage.pythonModule.withPackages (ps: [
                  ps.pytest
                  ps.pytest-testmon
                ]))
              ];
            }
            ''
              set -eu
              site="$(echo ${polyloguePackage}/lib/python*/site-packages)"
              test -d "$site/devtools"
              PYTHONPATH="$site''${PYTHONPATH:+:$PYTHONPATH}" python3 ${./pytest_admission.py}
              touch "$out"
            '';
        polylogue-runtime-inventory =
          pkgs.runCommand "sinnix-polylogue-runtime-inventory-check"
            {
              inherit sentinelDataDir;
              nativeBuildInputs = [ pkgs.jq ];
              actual = builtins.toJSON archiveInventory;
            }
            ''
              jq -e --arg root "$sentinelDataDir" '.archiveRoot == $root' <<<"$actual" >/dev/null
              touch "$out"
            '';
      };
    };
}
