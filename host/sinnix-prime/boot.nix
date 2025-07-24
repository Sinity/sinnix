# Host-specific boot configuration for sinnix-prime
{ ... }:
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
    blacklistedKernelModules = [
      "i915"
      "snd_sof_pci_intel_tgl"
      "snd_sof_intel_hda_common"
      "snd_sof_intel_hda"
      "snd_sof_pci"
      "snd_sof"
      "snd_soc_avs"
    ];
    extraModprobeConfig = ''
      options snd-intel-dspcfg dsp_driver=1
      options snd-hda-intel model=generic
    '';
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
