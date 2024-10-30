{ pkgs, ... }:
{
  boot.loader.systemd-boot.enable = true;
  boot.loader.efi.canTouchEfiVariables = true;
  boot.loader.systemd-boot.configurationLimit = null;
  boot.kernelPackages = pkgs.linuxPackages_latest;

  boot.kernel.sysctl."vm.swappiness" = 10;
  boot.kernelParams = [
    "quiet"
    "rw"
    "intel_pstate=disable"
    "cpufreq.default_governor=performance"

    "vconsole.keymap=pl"
    "vconsole.font=Lat2-Terminus16"
    "vconsole.font_map=8859-2"
    "vt.global_cursor_default=0"
    "loglevel=3"
    "rd.systemd.show_status=false"
    "rd.udev.log-priority=3"
    "acpi_enforce_resources=lax"
    "vga=current"
    "nowatchdog"
    "pti=off"
  ];
}
