# Contracts for the NVMe scratch root and its ownership-based sweeper.
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
      inherit (testLib) evalTestSpec mkRuntimeCheck;
      scriptRegistry = import ../scripts.nix { inherit inputs pkgs; };

      spec = testLib.mkFeatureTest {
        name = "tmp-sweep-placement";
        feature = "sinnix.profiles.workstation.enable";
        assertions =
          config:
          let
            user = config.sinnix.user.name;
            root = "/realm/tmp/${user}";
            sweeper = config.systemd.user.services.sinnix-tmp-sweep;
          in
          [
            {
              assertion = config.environment.sessionVariables.TMPDIR == root;
              message = "login sessions must place TMPDIR on the NVMe scratch root";
            }
            {
              assertion = config.systemd.user.settings.Manager.DefaultEnvironment == "TMPDIR=${root}";
              message = "the user manager must hand every unit the same scratch root";
            }
            {
              assertion = lib.any (r: r == "d ${root} 0700 ${user} users -") config.systemd.tmpfiles.rules;
              message = "the scratch root must exist, owned by the operator and unaged";
            }
            {
              assertion = config.systemd.user.timers ? sinnix-tmp-sweep;
              message = "the scratch sweeper must run on a timer, not on demand only";
            }
            {
              assertion = config.systemd.user.timers.sinnix-tmp-sweep.timerConfig.OnUnitActiveSec == "15min";
              message = "the sweeper cadence must be declared";
            }
            {
              assertion = lib.hasInfix "sinnix-tmp-sweep" sweeper.serviceConfig.ExecStart;
              message = "the sweeper unit must run the sweeper";
            }
          ];
      };
      evaluated = evalTestSpec system spec;
    in
    {
      checks.tmp-sweep-placement = evaluated.config.system.build.toplevel;

      # Anti-vacuity: a sweeper that removed nothing, or one that ignored a
      # live holder, both fail here. The two holders exercise the two ways a
      # directory is claimed -- a process sitting in it, and a process that
      # merely names it in TMPDIR while working elsewhere.
      checks.tmp-sweep-runtime = mkRuntimeCheck system {
        name = "tmp-sweep-runtime";
        nativeBuildInputs = [ scriptRegistry.packageSet.sinnix-tmp-sweep ];
        script = ''
          root="$HOME/scratch"
          mkdir -p "$root/nix-shell.leaked/deep" "$root/nix-shell.cwd" "$root/nix-shell.named"
          touch "$root/nix-shell.leaked/deep/file"

          ( cd "$root/nix-shell.cwd" && sleep 120 ) &
          cwd_holder=$!
          TMPDIR="$root/nix-shell.named" sleep 120 &
          named_holder=$!
          sleep 1

          TMPDIR="$root" sinnix-tmp-sweep | tee sweep.log

          kill "$cwd_holder" "$named_holder" 2>/dev/null || true

          test ! -e "$root/nix-shell.leaked"
          test -d "$root/nix-shell.cwd"
          test -d "$root/nix-shell.named"
          grep -q "root=$root removed=1 held=2 skipped=0" sweep.log
        '';
      };
    };
}
