{ inputs }:
final: _prev: {
  asbl-no-more = final.writeShellApplication {
    name = "asbl-no-more";
    runtimeInputs = with final; [
      bash
      coreutils
      procps
    ];
    text = ''
      exec ${final.bash}/bin/bash ${inputs.self}/scripts/asbl-no-more "$@"
    '';
  };

  hogkill = final.writeShellApplication {
    name = "hogkill";
    runtimeInputs = with final; [
      bash
      coreutils
      gum
      procps
      gawk
      gnugrep
      gnused
    ];
    text = ''
      exec ${final.bash}/bin/bash ${inputs.self}/scripts/hogkill "$@"
    '';
  };

  perf-scan = final.writeShellApplication {
    name = "perf-scan";
    runtimeInputs = with final; [
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
      # Use python3Packages to avoid version mismatch issues
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
      exec ${final.bash}/bin/bash ${inputs.self}/scripts/perf-scan "$@"
    '';
  };
}
