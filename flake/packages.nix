# ========================================
# PACKAGES: Custom packages for sinnix
# ========================================
#
# Use packages for:
# - Custom shell scripts wrapped with dependencies
# - Standalone utilities specific to sinnix
# - Tools not in nixpkgs
#
# Don't use packages for:
# - Modifications to existing nixpkgs packages → use overlays (flake/overlay/package/)
{ inputs, ... }:
{
  perSystem =
    {
      pkgs,
      system,
      ...
    }:
    {
      packages = {
        asbl-no-moar = pkgs.writeShellApplication {
          name = "asbl-no-moar";
          runtimeInputs = with pkgs; [
            bash
            coreutils
            procps
          ];
          text = ''
            exec ${pkgs.bash}/bin/bash ${inputs.self}/scripts/asbl-no-moar "$@"
          '';
        };

        hogkill = pkgs.writeShellApplication {
          name = "hogkill";
          runtimeInputs = with pkgs; [
            bash
            coreutils
            gum
            procps
            gawk
            gnugrep
            gnused
          ];
          text = ''
            exec ${pkgs.bash}/bin/bash ${inputs.self}/scripts/hogkill "$@"
          '';
        };

        perf-scan = pkgs.writeShellApplication {
          name = "perf-scan";
          runtimeInputs = with pkgs; [
            bash
            coreutils
            cpuid
            dmidecode
            ethtool
            fio
            flent
            gawk
            gnugrep
            gnused
            gum
            hw-probe
            hwdata
            i7z
            intel-gpu-tools
            inxi
            iperf3
            iproute2
            iw
            linuxPackages.turbostat
            lm_sensors
            mcelog
            memtester
            ncurses
            netperf
            nvme-cli
            numactl
            pciutils
            perf
            phoronix-test-suite
            powertop
            procps
            python3
            python3Packages.speedtest-cli
            rt-tests
            s-tui
            smartmontools
            stress-ng
            stressapptest
            sysbench
            sysstat
            usbutils
            util-linux
            glmark2
          ];
          text = ''
            exec ${pkgs.bash}/bin/bash ${inputs.self}/scripts/perf-scan "$@"
          '';
        };
      };
    };
}
