{ inputs }:
final: _prev:
let
  perfScanRuntimeInputs = with final; [
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
    python312Packages.speedtest-cli
    rt-tests
    s-tui
    smartmontools
    stress-ng
    stressapptest
    sysbench
    sysstat
    usbutils
    util-linux
    # vkmark
    glmark2
  ];
in
{
  perf-scan = final.writeShellApplication {
    name = "perf-scan";
    runtimeInputs = perfScanRuntimeInputs;
    text = ''
      exec ${final.bash}/bin/bash ${inputs.self}/scripts/perf-scan "$@"
    '';
  };
}
