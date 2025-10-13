{
  pkgs,
  username,
  ...
}:
{
  config = {
    environment = {
      systemPackages = with pkgs; [
        wget
        git

        hwinfo
        inxi
        dmidecode
        lshw
        pciutils
        usbutils

        btrfs-progs
        hdparm
        smartmontools
        nvme-cli

        iputils
        ethtool
        iftop
        iperf3

        mesa
        libGL
        libglvnd

        cpuid
        i7z
        mcelog
        memtester
        numactl
        hw-probe
        hwdata

        xfsprogs
        e2fsprogs
        lvm2
        parted
        fio
        ioping
        udisks2
        extundelete

        bpftrace
      ];
      variables.REALM_ROOT = "/realm";
    };

    programs = {
      direnv = {
        enable = true;
        silent = true;
        enableZshIntegration = true;
        enableBashIntegration = true;
        nix-direnv.enable = true;
      };

      dconf.enable = true;

      zsh =
        let
          ttyAutostart = ''
            if [ "$(id -un)" = "${username}" ] && [ -z "$DISPLAY" ]; then
              current_tty=$(tty 2>/dev/null || true)
              if [ "$current_tty" = "/dev/tty1" ]; then
                exec uwsm start hyprland-uwsm.desktop
              fi
            fi
          '';
        in
        {
          enable = true;
          loginShellInit = ttyAutostart;
        };

      gnupg.agent = {
        enable = true;
        enableSSHSupport = true;
      };
    };

    systemd.coredump.enable = true;

    services = {
      dbus.enable = true;

      earlyoom = {
        enable = true;
        enableNotifications = true;
        freeMemThreshold = 5;
        freeSwapThreshold = 5;
        reportInterval = 5;
        extraArgs = [
          "-g"
          "-p"
          "--prefer"
          "(^|/)(java|chromium|obsidian|google-chrome(-stable)?)$"
          "--avoid"
          "(^|/)(init|systemd|sshd)$"
        ];
      };

      gnome.gnome-keyring.enable = true;
    };
  };
}
