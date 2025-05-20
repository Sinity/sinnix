# Host-specific boot configuration for desktop
{ pkgs, ... }:
{
  boot = {
    loader = {
      systemd-boot = {
        enable = true;
        configurationLimit = null;
      };
      efi.canTouchEfiVariables = true;
    };

    # kernelPackages = pkgs.linuxPackages_latest;
    # kernelPackages = pkgs.linuxPackages_6_6;

    initrd.availableKernelModules = [
      "xhci_pci"
      "ahci"
      "nvme"
      "usbhid"
      "usb_storage"
      "sd_mod"
    ];
    blacklistedKernelModules = [ "i915" ];
    kernelModules = [ "kvm-intel" ];
    kernel.sysctl."vm.swappiness" = 10;
    kernelParams = [
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
    ];
  };
}
