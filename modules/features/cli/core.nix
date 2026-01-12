{ pkgs, mkFeatureModule, ... }@args:
mkFeatureModule {
  path = [ "cli" "core" ];
  description = "Core CLI environment";
  configFn =
    { config, pkgs, lib, ... }:
    let
      user = config.sinnix.user.name;
    in
    {
      environment.systemPackages = with pkgs; [
        git
        taskwarrior3
        timewarrior
        unzip
        wget
      ];

      programs = {
        zsh.enable = true;

        gnupg.agent = {
          enable = true;
          enableSSHSupport = true;
        };
      };

      systemd.coredump.enable = true;

      services = {
        dbus = {
          enable = true;
          implementation = "broker";
          brokerPackage = pkgs.dbus-broker;
        };

        gnome.gnome-keyring.enable = lib.mkForce false;
      };

      security.pam.services.login.enableGnomeKeyring = lib.mkForce false;

      home-manager.users.${user} =
        { lib, pkgs, ... }:
        {
          home.packages = lib.mkAfter (
            with pkgs;
            [
              nix-output-monitor
              nvd
              cachix
              nix-direnv
              killall
              procps
              psmisc
              iotop
              entr
              file
              tldr
              xdg-utils
              xxd
              graphicsmagick
              jq
              fzf
              bc
              at
              hledger
            ]
            ++ lib.filter (p: p != null) [
              (pkgs.tasksh or null)
              (pkgs.taskwarrior-tui or null)
              (pkgs.bugwarrior or null)
              (pkgs.timewarrior-all-reports or null)
            ]
          );

          programs.direnv = {
            enable = true;
            nix-direnv.enable = true;
            silent = true;
            config.global.warn_timeout = "30s";
          };

          programs.ssh = {
            enable = true;
            enableDefaultConfig = false;
            matchBlocks."*".addKeysToAgent = "yes";
          };

          programs.btop = {
            enable = true;
            settings = {
              vim_keys = true;
              update_ms = 2000;
              show_cpu_freq = true;
              show_gpu = true;
              mem_graphs = true;
              proc_sorting = "cpu direct";
              proc_filter = false;
              tree_view = false;
              proc_per_core = true;
              proc_mem_bytes = true;
              cpu_graph_upper = "total";
              cpu_graph_lower = "user";
              cpu_invert_lower = true;
            };
          };
        };
    };
} args
