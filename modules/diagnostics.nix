{
  pkgs,
  inputs,
  lib,
  ...
}:
let
  coreDiagnostics = with pkgs; [
    hwinfo
    inxi
    lshw
    smartmontools
    nvme-cli
    hdparm
  ];

  optionalDiagnostics = with pkgs; [
    cpuid
    dmidecode
    hw-probe
    hwdata
    i7z
    mcelog
    memtester
    numactl
    pciutils
    usbutils
  ];

  optionalPerfSuites = with pkgs; [
    flent
    netperf
    phoronix-test-suite
    stress-ng
    stressapptest
    sysbench
    s-tui
    lm_sensors
    perf
  ];

  perfScanRuntimeInputs = with pkgs; [
    bash
    bc
    coreutils
    ethtool
    findutils
    flent
    gawk
    gnugrep
    gum
    hdparm
    intel-gpu-tools
    inxi
    iperf3
    iproute2
    jq
    linuxPackages.turbostat
    lm_sensors
    memtester
    netperf
    nvme-cli
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
    util-linux
    vkmark
    glmark2
  ];

  perfScan = pkgs.writeShellApplication {
    name = "perf-scan";
    runtimeInputs = perfScanRuntimeInputs;
    text = builtins.readFile "${inputs.self}/scripts/perf-scan";
  };
in
{
  options.sinnix.optionalPackages = lib.mkOption {
    type = lib.types.attrsOf (lib.types.listOf lib.types.package);
    default = { };
    description = "Optional package groups that are not installed by default.";
    readOnly = true;
  };

  config = {
    environment.systemPackages = lib.mkAfter (coreDiagnostics ++ [ perfScan ]);
    sinnix.optionalPackages = {
      diagnostics = optionalDiagnostics;
      perfSuites = optionalPerfSuites;
      perfScanRuntime = perfScanRuntimeInputs;
    };
  };
}
