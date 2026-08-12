# PRIMARY-selection capture lane: static service-shape checks (unit
# ExecStart/Environment/ReadWritePaths, runtime surface metadata).
#
# No runtime fixture here (unlike capture-clipboard.nix's
# heavyChecks.capture-clipboard-runtime): the generated watch script is a
# `pkgs.writeShellApplication` whose `runtimeInputs` (wl-clipboard,
# hyprland) get baked into its own `export PATH="<real nix store
# paths>:$PATH"` line ahead of anything a test fixture puts on the outer
# PATH, so a fixture `wl-paste`/`hyprctl` earlier on the caller's PATH is
# always shadowed by the real ones -- and the real ones fail immediately
# in the hermetic build sandbox (no Wayland socket), so nothing is ever
# captured. This is a structural property of the shared writeShellApplication
# + runtimeInputs pattern, not specific to this lane; capture-clipboard's
# existing runtime fixture has the identical shadowing problem (verified
# 2026-08-12 empirically, both live and in-sandbox) and cannot exercise its
# fixture data either. Fixing it for real needs the watch script's
# wl-paste/hyprctl resolution to be overridable per-test (e.g. via a
# nixpkgs overlay swapping pkgs.wl-clipboard/pkgs.hyprland for fixture
# stand-ins) -- a cross-cutting change to the shared pattern, out of scope
# here. The watch script's actual runtime behavior (including the debounce
# burst-collapse this module adds) was verified live against a real
# Wayland session instead; see the module header and the commit history
# for that evidence.
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
              .kind == "capture" and
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
