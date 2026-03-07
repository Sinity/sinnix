{ pkgs, mkFeatureModule, ... }@args:
mkFeatureModule {
  path = [
    "cli"
    "core"
  ];
  description = "Core CLI environment";
  configFn =
    {
      config,
      pkgs,
      lib,
      user,
      ...
    }:
    {
      environment.systemPackages = with pkgs; [
        git
        taskwarrior3
        timewarrior
        repomix
        difftastic
        unzip
        wget
        # Modern CLI replacements
        eza
        bat
        fd
        lnav
        dua
        bandwhich
        # Even more modern tools
        micro
        bottom
        gping
        doggo
        dust
      ];

      programs = {
        zsh.enable = true;

        gnupg.agent = {
          enable = true;
          enableSSHSupport = true;
        };
      };

      systemd.coredump.enable = true;

      # Disable GNOME keyring - using GPG agent for SSH key management instead
      services.gnome.gnome-keyring.enable = lib.mkForce false;

      # Prevent PAM from starting keyring on login (conflicts with gpg-agent SSH)
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
              procs
              psmisc
              iotop
              entr
              file
              tldr
              xdg-utils
              xxd
              jq
              fzf
              bc
              at
              speedtest-cli
              stress-ng
              glances
            ]
            ++ lib.filter (p: p != null) [
              (pkgs.tasksh or null)
              (pkgs.taskwarrior-tui or null)
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
            matchBlocks = {
              "*".addKeysToAgent = "yes";
              # Router: `ssh sinnix-gw` just works
              "sinnix-gw" = {
                hostname = "192.168.1.1";
                user = "root";
              };
              "sinnix-gw.lan" = {
                hostname = "192.168.1.1";
                user = "root";
              };
            };
          };

          programs.btop = {
            enable = true;
            settings = {
              vim_keys = true;
              update_ms = 2000;
              show_cpu_freq = true;
              show_gpu = true;
              mem_graphs = true;
              proc_sorting = "cpu descending";
              proc_filter = true;
              tree_view = true;
              proc_gradient = true;
              proc_per_core = true;
              proc_mem_bytes = true;
              proc_left = true;
              proc_aggregate = true;
              cpu_graph_upper = "total";
              cpu_graph_lower = "user";
              cpu_invert_lower = true;
              show_uptime = true;
              check_temp = true;
            };
          };
        };
    };
} args
