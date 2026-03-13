# Host-specific boot configuration for sinnix-prime
{ pkgs, lib, inputs, ... }:
{
  imports = [ inputs.lanzaboote.nixosModules.lanzaboote ];

  boot = {
    lanzaboote = {
      enable = true;
      pkiBundle = "/var/lib/sbctl";
      autoGenerateKeys.enable = true;
    };

    loader = {
      systemd-boot = {
        enable = lib.mkForce false;
        configurationLimit = null;
      };
      efi.canTouchEfiVariables = true;
    };

    kernelPackages = pkgs.linuxPackages;

    initrd.availableKernelModules = [
      "xhci_pci"
      "ahci"
      "nvme"
      "usbhid"
      "usb_storage"
      "sd_mod"
    ];
    blacklistedKernelModules = [
      "i915"
    ];
    kernelModules = [ "kvm-intel" ];
    kernelParams = [
      "quiet"
      "rw"
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

  environment.systemPackages = [ pkgs.sbctl ];
  sinnix.persistence.system.directories = [ "/var/lib/sbctl" ];

  # intel_pstate on this host exposes performance/powersave governors;
  # forcing schedutil makes NixOS try to load cpufreq_schedutil at boot.
  powerManagement.cpuFreqGovernor = "powersave";
  hardware.enableRedistributableFirmware = true;
}
