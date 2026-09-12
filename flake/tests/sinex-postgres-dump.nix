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
      evaluated = testLib.evalTestSpec system {
        name = "sinex-postgres-dump";
        assertions = _: [ ];
        specialArgs.secretDeclarations.sinex-local-db.file = pkgs.writeText "synthetic.age" "fixture";
        modules = [
          testLib.mountTmpfsRoots
          testLib.baseTestConfig
          inputs.sinex.nixosModules.default
          ../../modules/services/sinex/bridge.nix
          ({ ... }: {
            sinnix.secrets.enable = lib.mkForce true;
            sinnix.services.sinex.enable = true;
          })
        ];
      };
      script = pkgs.writeShellScript "sinex-postgres-dump-fixture" (
        lib.replaceStrings
          [ "/realm/state/db-dumps/sinex-postgres" "/run/agenix/sinex-local-db" ]
          [ "./dumps" "./password" ]
          evaluated.config.systemd.services.sinex-postgres-dump.script
      );
    in
    {
      checks.sinex-postgres-dump =
        pkgs.runCommand "sinex-postgres-dump-check"
          {
            nativeBuildInputs = [
              pkgs.python3
              pkgs.bash
              pkgs.coreutils
            ];
          }
          ''
            mkdir -p bin dumps
            printf '%s\n' fixture-password > password
            cat > bin/install <<'EOF'
            #!${pkgs.bash}/bin/bash
            # Unit ownership is applied by systemd; the sandbox has no postgres user.
            args=()
            while [ "$#" -gt 0 ]; do
              case "$1" in
                -o|-g) shift 2 ;;
                *) args+=("$1"); shift ;;
              esac
            done
            exec ${pkgs.coreutils}/bin/install "''${args[@]}"
            EOF
            cat > bin/pg_dump <<'EOF'
            #!${pkgs.bash}/bin/bash
            set -euo pipefail
            for arg in "$@"; do
              case "$arg" in --file=*) output="''${arg#--file=}" ;; esac
            done
            printf '%s\n' dump-payload > "$output"
            exit "''${DUMP_STATUS:-0}"
            EOF
            chmod +x bin/*
            export PATH="$PWD/bin:$PATH"
            export DUMP_COMMAND=${script}
            python3 - <<'PY'
            import os, pathlib, stat, subprocess
            root = pathlib.Path("dumps")
            originals = {}
            for number in range(20):
                path = root / f"sinex_prod-20000101T0000{number:02d}Z.dump"
                payload = f"historical version {number}\n".encode()
                path.write_bytes(payload)
                originals[path] = payload
            subprocess.run([os.environ["DUMP_COMMAND"]], check=True)
            for path, payload in originals.items():
                assert path.read_bytes() == payload
            created = set(root.iterdir()) - originals.keys()
            assert len(created) == 1, created
            output = created.pop()
            assert output.read_bytes() == b"dump-payload\n"
            assert stat.S_IMODE(output.stat().st_mode) == 0o600
            before_failure = {p: p.read_bytes() for p in root.iterdir()}
            failed = subprocess.run([os.environ["DUMP_COMMAND"]], env={**os.environ, "DUMP_STATUS": "45"})
            assert failed.returncode == 45
            assert {p: p.read_bytes() for p in root.iterdir()} == before_failure
            PY
            touch "$out"
          '';
    };
}
