# Polylogue service module evaluation checks.
#
# The live wrapper is the daemon's command and the browser host, so both must
# name the same archive; the host manifest must allow the ID Chrome derives
# from the extension directory.
#
# Provably fails when: the unit's ExecStart or the host manifest stops going
# through the polylogue wrapper, or the extension ID derivation changes
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
        polylogue-command-binding =
          let
            probe = pkgs.writeShellScriptBin "polylogue" ''
              set -euo pipefail
              test "$POLYLOGUE_HTTP_PORT" = ${toString (import ../data/ports.nix).polylogue.web}
              test "$XDG_DATA_HOME" = "$EXPECTED_DATA_HOME"
              test "$XDG_STATE_HOME" = "$EXPECTED_STATE_HOME"
              test -z "''${POLYLOGUE_ARCHIVE+x}"
              test -z "''${POLYLOGUE_HOME+x}"
              test "$1" = mcp
              test "$2" = 'one argument'
            '';
            wrapper =
              mode:
              import ../../modules/lib/polylogue-cli.nix {
                inherit lib pkgs;
                inputs.polylogue-rewrite.packages.${system}.polylogue = probe;
                config.sinnix.services.polylogue = {
                  sinex.mode = mode;
                  liveRoot = "/fixture/live archive";
                };
              };
            mcp =
              cli:
              (import ../../modules/features/dev/agents/mcp-tools.nix {
                inherit lib pkgs;
                scriptPkgs = { };
                config.system.build.polylogueCli = cli;
              }).mcpPolylogueBin;
          in
          pkgs.runCommand "polylogue-command-binding" { } ''
            export POLYLOGUE_HTTP_PORT=1
            export XDG_DATA_HOME=/foreign/data XDG_STATE_HOME=/foreign/state
            export POLYLOGUE_ARCHIVE=/foreign/archive POLYLOGUE_HOME=/foreign/home
            export EXPECTED_STATE_HOME='/fixture/live archive/state'
            export EXPECTED_DATA_HOME='/fixture/live archive/data'
            ${wrapper "standalone"}/bin/polylogue mcp 'one argument'
            ${(mcp (wrapper "standalone"))}/bin/mcp-polylogue 'one argument'
            export EXPECTED_DATA_HOME='/fixture/live archive/sinex-data'
            ${wrapper "primary"}/bin/polylogue mcp 'one argument'
            ${(mcp (wrapper "primary"))}/bin/mcp-polylogue 'one argument'
            ${pkgs.python3}/bin/python ${./polylogue-mcp.py} ${(mcp liveEvaluated.config.system.build.polylogueCli)}/bin/mcp-polylogue
            touch "$out"
          '';
        polylogue-live =
          pkgs.runCommand "sinnix-polylogue-live-check"
            {
              nativeBuildInputs = [ pkgs.jq ];
              execStart = liveService.Service.ExecStart;
              cli = liveEvaluated.config.system.build.polylogueCli;
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
              test "$execStart" = "$cli/bin/polylogue daemon"
              case "$wrapper" in */bin/polylogue) ;; *) exit 1 ;; esac
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
        polylogue-runtime-inventory =
          pkgs.runCommand "sinnix-polylogue-runtime-inventory-check"
            {
              archiveRoot = "${liveRoot}/data/polylogue";
              nativeBuildInputs = [ pkgs.jq ];
              actual = builtins.toJSON archiveInventory;
            }
            ''
              jq -e --arg root "$archiveRoot" '.archiveRoot == $root' <<<"$actual" >/dev/null
              touch "$out"
            '';
      };
    };
}
