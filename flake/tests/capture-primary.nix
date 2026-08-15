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
      surface = evaluated.config.sinnix.runtime.surfaces.capture-primary;
      unitJson = builtins.toJSON {
        Unit = unit.Unit;
        Service = unit.Service;
      };
      surfaceJson = builtins.toJSON surface;
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
            cat > surface.json <<'EOF_SURFACE'
            ${surfaceJson}
            EOF_SURFACE
            jq -e '
              # ExecStart may render as a plain string or a single-element
              # array depending on the systemd option merge/apply behavior
              # -- normalize before substring checks.
              (.Service.ExecStart | if type == "array" then join(" ") else . end) as $execStart |
              ($execStart | contains("wl-paste --primary --watch")) and
              ($execStart | contains("sinnix-capture-primary-watch")) and
              (.Service.Environment | any(startswith("SINNIX_CAPTURE_ROOT="))) and
              (.Service.Environment | any(startswith("SINNIX_CAPTURE_PRIMARY_STATE_DIR="))) and
              (.Service.Environment | any(startswith("SINNIX_CAPTURE_PRIMARY_DEBOUNCE_MS="))) and
              (.Service.ReadWritePaths | length) == 3 and
              .Unit.After == ["graphical-session.target"] and
              .Unit.PartOf == ["graphical-session.target"]
            ' unit.json >/dev/null
            jq -e '
              .resourceClass == "capture-runtime" and
              .kind == "service" and
              .manager == "user" and
              (.captures[0].eventDriven) and
              .captures[0].staleAfterSeconds == 604800 and
              .observe.enable and
              .observe.restartable
            ' surface.json >/dev/null
            touch "$out"
          '';
    };
}
