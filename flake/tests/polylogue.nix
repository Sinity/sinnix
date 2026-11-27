# Polylogue service module evaluation checks.
#
# The live wrapper is the daemon's command and the browser host, so both must
# name the same archive; the host manifest allows the packaged extension ID.
#
# Provably fails when: the unit's ExecStart or the host manifest stops going
# through the polylogue wrapper, or the configured extension and manifest
# disagree.
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
      extension = inputs.polylogue-rewrite.packages.${system}.polylogue-extension;
      linkedExtension = hm.xdg.dataFile."polylogue/extension";
      hostManifest =
        hm.home.file.".config/chrome-ws/NativeMessagingHosts/com.polylogue.browser_capture.json".source;
      polylogueTmpfiles = liveEvaluated.config.systemd.tmpfiles.rules;
      archiveInventory = liveEvaluated.config.sinnix.runtime.inventory.polylogue;
    in
    {
      checks = {
        polylogue-command-binding =
          let
            probe = pkgs.writeShellScriptBin "polylogue" ''
              set -euo pipefail
              test "$XDG_DATA_HOME" = "$EXPECTED_DATA_HOME"
              test "$XDG_STATE_HOME" = "$EXPECTED_STATE_HOME"
              test -z "''${POLYLOGUE_ARCHIVE+x}"
              test -z "''${POLYLOGUE_HOME+x}"
              test "''${POLYLOGUE_MCP_SOCKET:-}" = "''${EXPECTED_MCP_SOCKET:-}"
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
                  dataHome = "/fixture/live archive/${if mode == "primary" then "sinex-data" else "data"}";
                };
                config.sinnix.user.name = "op";
                config.users.users.op.home = "/fixture/home";
              };
            mcp =
              cli: mcpSocket:
              (import ../../modules/features/dev/agents/mcp-tools.nix {
                inherit lib pkgs inputs;
                scriptPkgs = { };
                config.system.build.polylogueCli = cli;
                config.sinnix.services.polylogue.mcpSocket = mcpSocket;
              }).mcpPolylogueBin;
            endpoint = "/run/user/1234/polylogue-mcp.sock";
          in
          pkgs.runCommand "polylogue-command-binding" { } ''
            export XDG_DATA_HOME=/foreign/data XDG_STATE_HOME=/foreign/state
            export POLYLOGUE_ARCHIVE=/foreign/archive POLYLOGUE_HOME=/foreign/home
            export EXPECTED_STATE_HOME=/fixture/home/.local/state
            export EXPECTED_DATA_HOME='/fixture/live archive/data'
            ${wrapper "standalone"}/bin/polylogue mcp 'one argument'
            EXPECTED_MCP_SOCKET=${endpoint} ${(mcp (wrapper "standalone") endpoint)}/bin/mcp-polylogue 'one argument'
            export EXPECTED_DATA_HOME='/fixture/live archive/sinex-data'
            ${wrapper "primary"}/bin/polylogue mcp 'one argument'
            EXPECTED_MCP_SOCKET=${endpoint} ${(mcp (wrapper "primary") endpoint)}/bin/mcp-polylogue 'one argument'
            # Polylogue reads /etc/machine-id at start-up and the build sandbox
            # has none: run the MCP check with a copy of /etc that has one.
            mkdir etc
            cp -r /etc/. etc/
            echo 00000000000000000000000000000001 > etc/machine-id
            ${pkgs.util-linux}/bin/unshare --user --map-root-user --mount ${pkgs.bash}/bin/sh -c \
              '${pkgs.util-linux}/bin/mount --bind "$PWD/etc" /etc && exec "$0" "$@"' \
              ${pkgs.python3}/bin/python ${./polylogue-mcp.py} ${(mcp liveEvaluated.config.system.build.polylogueCli liveEvaluated.config.sinnix.services.polylogue.mcpSocket)}/bin/mcp-polylogue
            touch "$out"
          '';
        polylogue-live =
          assert linkedExtension.recursive;
          assert toString linkedExtension.source == "${extension}/share/polylogue/extension";
          pkgs.runCommand "sinnix-polylogue-live-check"
            {
              nativeBuildInputs = [ pkgs.jq ];
              execStart = liveService.Service.ExecStart;
              cli = liveEvaluated.config.system.build.polylogueCli;
              wantedBy = builtins.toJSON liveService.Install.WantedBy;
              servicePolicy = builtins.toJSON liveService.Service;
              endpoint = liveEvaluated.config.sinnix.services.polylogue.mcpSocket;
              inherit extension hostManifest;
            }
            ''
              set -eu
              jq -e --arg endpoint "$endpoint" '.Environment | index("POLYLOGUE_MCP_SOCKET=" + $endpoint) != null' <<<"$servicePolicy"
              case "$endpoint" in /run/user/[0-9]*/polylogue-mcp.sock) ;; *) exit 1 ;; esac
              id="$(cat "$extension/share/polylogue/extension-id")"
              wrapper="''${execStart% daemon}"
              test "$execStart" = "$cli/bin/polylogue daemon"
              case "$wrapper" in */bin/polylogue) ;; *) exit 1 ;; esac
              jq -e 'index("default.target") != null' <<<"$wantedBy" >/dev/null
              jq -e '
                .Slice == "live.slice" and (has("IOWeight") | not) and
                (has("Nice") | not) and (has("IOSchedulingPriority") | not) and
                (has("MemoryHigh") | not) and .MemoryMax == "8G" and
                .MemorySwapMax == "1G"
              ' <<<"$servicePolicy" >/dev/null
              jq -e --arg wrapper "$wrapper" --arg id "$id" '
                .path == $wrapper and
                .allowed_origins == ["chrome-extension://\($id)/"]
              ' "$hostManifest" >/dev/null
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
