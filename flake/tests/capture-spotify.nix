# Spotify capture contract checks.
#
# Provably fails when: the lane loses its five-minute timer, capture-runtime
# admission, secret wiring, shared envelope writer, or played_at cursor
# comparison. The source checks also protect the millisecond boundary and
# repeated-play behavior: changing `>` to `>=` or removing the timestamp sort
# makes the corresponding assertion fail.
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
      inherit (testLib) evalTestSpec mkServiceTest;
      spec = mkServiceTest {
        name = "capture-spotify";
        service = "capture-spotify";
        assertions = _: [ ];
      };
      evaluated = evalTestSpec system spec;
      unit = evaluated.config.systemd.user.services.sinnix-capture-spotify;
      timer = evaluated.config.systemd.user.timers.sinnix-capture-spotify;
      captures = evaluated.config.sinnix.runtime.inventory.captures;
      source = builtins.readFile ../../modules/services/capture-spotify.nix;
      unitJson = builtins.toJSON unit;
      timerJson = builtins.toJSON timer;
      capturesJson = builtins.toJSON captures;
    in
    {
      checks.capture-spotify-static =
        pkgs.runCommand "capture-spotify-static-check"
          { nativeBuildInputs = [ pkgs.jq ]; }
          ''
            cat > unit.json <<'EOF_UNIT'
            ${unitJson}
            EOF_UNIT
            cat > timer.json <<'EOF_TIMER'
            ${timerJson}
            EOF_TIMER
            cat > captures.json <<'EOF_CAPTURES'
            ${capturesJson}
            EOF_CAPTURES
            jq -e '
              (.serviceConfig.ExecStart | contains("capture-spotify-poll")) and
              (.serviceConfig.ExecStart | contains("spotify-client-id")) and
              (.serviceConfig.ExecStart | contains("spotify-client-secret")) and
              (.serviceConfig.ExecStart | contains("spotify-refresh-token")) and
              (.serviceConfig.ExecStart | contains("sinnix-capture")) and
              (.serviceConfig.ReadWritePaths | any(contains("/spotify")))
            ' unit.json >/dev/null
            jq -e '
              .timerConfig.OnUnitActiveSec == "300s" and
              .timerConfig.OnBootSec == "2min" and
              .timerConfig.AccuracySec == "30s"
            ' timer.json >/dev/null
            jq -e '
              map(select(.name == "spotify")) | length == 1 and
              .[0].path | endswith("/activity/spotify") and
              .[0].expectedCadenceSeconds == 300 and
              .[0].expectedStaleAfterSeconds == 600 and
              .[0].eventDriven == true
            ' captures.json >/dev/null
            cat > source.txt <<'EOF_SOURCE'
            ${source}
            EOF_SOURCE
            grep -F 'map(select(._played_at_ms > $after_ms))' source.txt >/dev/null
            grep -F 'sort_by(._played_at_ms)' source.txt >/dev/null
            grep -F 'max_ms' source.txt >/dev/null
            grep -F "no refresh token -- run 'sinnix spotify-auth'" source.txt >/dev/null
            touch "$out"
          '';
    };
}
