# Provably fails when: the lane's directory moves out from under the capture
# root the unit is given, or the unit loses write access to the lane the
# runtime inventory advertises for it.
#
# PRIMARY-selection capture lane: static service-shape checks (unit
# ExecStart/Environment/ReadWritePaths, runtime surface metadata).
#
# No runtime fixture here yet. One can follow the stripped-PATH copy +
# patchShebangs recipe in flake/tests/capture-clipboard.nix, which solves
# the writeShellApplication-baked PATH shadowing fixture fakes and the
# missing /usr/bin/env in the sandbox; it additionally needs the debounce
# collapsed (debounceMs = 0) so a single fixture invocation writes
# synchronously.
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
        name = "capture-primary";
        service = "capture-primary";
        assertions = _: [ ];
      };
      evaluated = evalTestSpec system spec;
      hm = evaluated.config.home-manager.users.${evaluated.config.sinnix.user.name};
      unit = hm.systemd.user.services.sinnix-capture-primary;
      unitJson = builtins.toJSON {
        Unit = unit.Unit;
        Service = unit.Service;
      };
      capturesJson = builtins.toJSON evaluated.config.sinnix.runtime.inventory.captures;
    in
    {
      checks.capture-primary-static =
        pkgs.runCommand "capture-primary-static-check"
          {
            nativeBuildInputs = [ pkgs.jq ];
          }
          ''
            cat > unit.json <<'EOF_UNIT'
            ${unitJson}
            EOF_UNIT
            cat > captures.json <<'EOF_CAPTURES'
            ${capturesJson}
            EOF_CAPTURES
            jq -e '
              # ExecStart may render as a plain string or a single-element
              # array depending on the systemd option merge/apply behavior
              # -- normalize before substring checks.
              (.Service.ExecStart | if type == "array" then join(" ") else . end) as $execStart |
              ($execStart | contains("wl-paste --primary --watch")) and
              ($execStart | contains("sinnix-capture-primary-watch")) and
              .Unit.After == ["graphical-session.target"] and
              .Unit.PartOf == ["graphical-session.target"]
            ' unit.json >/dev/null
            # The lane the sentinel watches and the directory the unit is
            # actually allowed to write must be the same place: a lane
            # advertised at a path no unit writes is a silent capture gap.
            # Neither side is restated as a literal here.
            jq -e --slurpfile captures captures.json --arg lane "primary" '
              (.Service.Environment
                | map(select(startswith("SINNIX_CAPTURE_ROOT=")))
                | first
                | ltrimstr("SINNIX_CAPTURE_ROOT=")) as $root |
              ($captures[0] | map(select(.name == $lane)) | first) as $capture |
              $root != null and
              $capture != null and
              ($capture.path | startswith($root + "/")) and
              (.Service.ReadWritePaths | any($capture.path | startswith(.)))
            ' unit.json >/dev/null
            touch "$out"
          '';
    };
}
