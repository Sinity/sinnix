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
      helpers,
      ...
    }:
    let
      scriptPkgs = helpers.mkSinnixPackagesFor pkgs;
    in
    {
      environment.systemPackages =
        (with pkgs; [
          git
          taskwarrior3
          timewarrior
          repomix
          difftastic
          bubblewrap
          unzip
          wget
          # age: same crypto as agenix. Kept system-wide so the master-key
          # escrow blob (see knowledgebase docs/sinnix-key-recovery.md) can be
          # created and, more importantly, decrypted during disaster recovery
          # without fetching tools.
          age
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
        ])
        # `sinnix` -- discoverable front door over the whole packaged script
        # registry (`sinnix help`, `sinnix <name> [args...]`).
        ++ [ scriptPkgs.sinnix ];

      programs = {
        zsh.enable = true;

        gnupg.agent = {
          enable = true;
          enableSSHSupport = true;
        };
      };

      systemd.coredump = {
        enable = true;
        settings.Coredump = {
          Storage = "none";
          ProcessSizeMax = "128M";
          ExternalSizeMax = "0";
          JournalSizeMax = "8M";
        };
      };
      services.atd.enable = true;

      # Disable GNOME keyring - using GPG agent for SSH key management instead
      services.gnome.gnome-keyring.enable = lib.mkForce false;

      # Prevent PAM from starting keyring on login (conflicts with gpg-agent SSH)
      security.pam.services.login.enableGnomeKeyring = lib.mkForce false;

      # Drop pam_lastlog2 from the login stack: last-login display is
      # worthless on this single-operator host, it issues a root-SSD SQLite
      # write on every session open, and its SQLite access has no busy
      # timeout, so concurrent agent session storms failed PAM session setup
      # outright. (mkForce: upstream pam.nix asserts enable = true.)
      security.pam.services.login.rules.session.lastlog.enable = lib.mkForce false;

      home-manager.users.${user} =
        {
          lib,
          pkgs,
          config,
          ...
        }:
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
              fio
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

          xdg.configFile."direnv/direnvrc".text = builtins.readFile ../../../scripts/sinnix-direnvrc;

          programs.ssh = {
            enable = true;
            enableDefaultConfig = false;
            settings = {
              "*".AddKeysToAgent = "yes";
              # GitHub automation must never depend on gpg-agent cache state or
              # pinentry. The dedicated transport key is unencrypted and
              # intentionally available to unattended local agents.
              "github.com" = {
                HostName = "github.com";
                User = "git";
                IdentityFile = "/home/sinity/.ssh/id_ed25519";
                IdentitiesOnly = true;
                IdentityAgent = "none";
                BatchMode = true;
                AddKeysToAgent = "no";
              };
              # Router: `ssh sinnix-gw` just works
              "sinnix-gw" = {
                HostName = "192.168.1.1";
                User = "root";
              };
              "sinnix-gw.lan" = {
                HostName = "192.168.1.1";
                User = "root";
              };
              # Phone (Redmi Note 11) over the tailnet, Termux sshd. The user
              # is Termux's per-install Android UID, not a stable name.
              "phone" = {
                HostName = "100.124.215.25";
                User = "u0_a398";
                Port = 8022;
                ServerAliveInterval = 30;
              };
            };
          };

          # Desktop -> phone clipboard push (sinnix-uyvt.5). One-way only:
          # Android blocks clipboard READS from a backgrounded app, so the
          # phone->desktop half is not attempted here -- see the header
          # comment in scripts/sinnix-phone. wl-paste --watch blocks on
          # clipboard change, so this is push-triggered, not a poll loop.
          systemd.user.services.sinnix-phone-clip-watch = {
            Unit = {
              Description = "Push desktop clipboard changes to the phone over the tailnet";
              After = [ "graphical-session.target" ];
              PartOf = [ "graphical-session.target" ];
            };
            Service = {
              Type = "simple";
              ExecStart = "${scriptPkgs.sinnix-phone}/bin/sinnix-phone clip-watch";
              Restart = "on-failure";
              RestartSec = "10s";
            };
            Install.WantedBy = [ "graphical-session.target" ];
          };

          programs.bat = {
            enable = true;
            config.pager = "less -FR";
            # theme: set by stylix (stylix.targets.bat)
          };

          programs.broot = {
            enable = true;
            enableZshIntegration = true;
            # Home Manager owns ~/.config/broot now. Keep the custom skin, modal
            # mode, special paths, and verbs in the canonical dots JSON source.
            settings = builtins.fromJSON (builtins.readFile ../../../dots/broot/conf.hjson);
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
