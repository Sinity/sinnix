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
      # Removing SOF/AVS blacklist to test if it helps with binding
      # "snd_sof_pci_intel_tgl"
      # "snd_sof_intel_hda_common"
      # "snd_sof_intel_hda"
      # "snd_sof_pci"
      # "snd_sof"
      # "snd_soc_avs"
    ];
    extraModprobeConfig = ''
      # Intel HDA audio troubleshooting attempts (none worked for binding issue):
      # - dsp_driver=1: Forces legacy HDA mode (non-SOF)
      # - model=generic/auto: Different codec detection methods
      # - position_fix=3: Workaround for some Intel chips
      # - probe_mask=1: Forces probing first codec only
      # - dmic_detect=0: Disables digital microphone detection
      # - enable=1,0: Enables first device, disables second (HDMI)
      # Error persists: "couldn't bind with audio component"
      options snd-intel-dspcfg dsp_driver=1
      options snd-hda-intel model=auto dmic_detect=0 enable=1,0
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
      
      # Force Intel HDA to use legacy driver for aux/line-in support
      "snd-intel-dspcfg.dsp_driver=1"
    ];
  };
}
