# Deploy mechanisms.
#
# Two complementary tools:
#
#   nixos-anywhere — first-boot bootstrap. Used once, to seed
#     sinnix-ethereal from the default Hetzner image into a real NixOS
#     install (partitions via disko, transfers system closure over SSH).
#
#   colmena        — steady-state declarative deploys. Reads
#     `colmena.hive` and pushes per-host nixosConfigurations to their
#     deployment targets. Tags map to the per-host names.
#
# Exposed convenience scripts (run via `nix run .#<name>`):
#
#   deploy-ethereal HOSTNAME-OR-IP   — wraps nixos-anywhere for the first boot
#   apply-all                        — colmena apply --on @all
#
# Operator prereqs before either script becomes useful:
#
#   1. Provision the Hetzner AX42 in the robot console.
#   2. Generate a Tailscale auth key in the admin console with
#      tag:infra preauthorized.
#   3. `agenix -e secret/tailscale-authkey.age` with that key.
#   4. `agenix -e secret/sinex-remote-db.age` once postgres credentials are
#      decided.
#   5. `agenix -e secret/borg-storagebox-ssh.age` once the StorageBox is up.
{ inputs, ... }:
{
  flake.colmena = {
    meta = {
      nixpkgs = import inputs.nixpkgs {
        system = "x86_64-linux";
      };
      specialArgs = {
        inherit inputs;
      };
    };

    sinnix-prime = {
      deployment = {
        targetHost = "sinnix-prime";
        targetUser = "root";
        tags = [
          "workstation"
          "primary"
        ];
      };
      imports = [
        inputs.self.nixosConfigurations.sinnix-prime.config.system.build.toplevel
      ];
    };

    sinnix-ethereal = {
      deployment = {
        # Override at deploy time via `colmena apply --on sinnix-ethereal --target-host ...`
        # until the tailnet hostname stabilizes.
        targetHost = "sinnix-ethereal";
        targetUser = "root";
        tags = [
          "infra"
          "replica"
        ];
      };
      imports = [
        inputs.self.nixosConfigurations.sinnix-ethereal.config.system.build.toplevel
      ];
    };
  };

  perSystem =
    {
      pkgs,
      system,
      ...
    }:
    {
      packages = {
        deploy-ethereal = pkgs.writeShellApplication {
          name = "deploy-ethereal";
          runtimeInputs = [
            inputs.nixos-anywhere.packages.${system}.nixos-anywhere
          ];
          text = ''
            # Usage: deploy-ethereal <root@host-or-ip>
            #
            # First-boot bootstrap. Wipes the target disks per
            # hosts/sinnix-ethereal/disko.nix and installs the
            # sinnix-ethereal flake output. Requires SSH access as root to
            # a running rescue/installer system on the AX42.
            set -euo pipefail
            if [[ $# -lt 1 ]]; then
              echo "usage: deploy-ethereal <root@host-or-ip>" >&2
              exit 64
            fi
            target="$1"
            shift
            exec nixos-anywhere \
              --flake .#sinnix-ethereal \
              --target-host "$target" \
              "$@"
          '';
        };

        apply-all = pkgs.writeShellApplication {
          name = "apply-all";
          runtimeInputs = [
            inputs.colmena.packages.${system}.colmena
          ];
          text = ''
            # Usage: apply-all [colmena-args...]
            #
            # Steady-state push of every host in the colmena.hive to its
            # deployment target. Common invocations:
            #   apply-all                       # apply --on @all
            #   apply-all --on infra            # only infra-tagged hosts
            #   apply-all --keep-result         # retain result symlinks
            set -euo pipefail
            if [[ $# -eq 0 ]]; then
              exec colmena apply --on @all
            else
              exec colmena apply "$@"
            fi
          '';
        };
      };
    };
}
