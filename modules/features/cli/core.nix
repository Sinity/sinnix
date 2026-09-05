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
          # escrow blob (knowledgebase docs/sinnix-key-recovery.md) can be
          # decrypted during disaster recovery without fetching tools.
          age
          eza
          bat
          fd
          lnav
          dua
          bandwhich
          micro
          bottom
          gping
          doggo
          dust
          arp-scan
          nmap
        ])
        # `sinnix` -- discoverable front door over the whole packaged script
        # registry (`sinnix help`, `sinnix <name> [args...]`).
        ++ [ scriptPkgs.sinnix ];

      programs = {
        zsh.enable = true;

        gnupg.agent = {
          enable = true;
          enableSSHSupport = true;
          # Effectively-infinite SSH cache TTLs. gpg-agent re-prompts through
          # pinentry once its cache expires (upstream: 30 minutes soft, 2 hours
          # hard), which interrupts unattended work and protects nothing here:
          # local agents already have sudo NOPASSWD and nix trusted-users, and
          # ~/.ssh/id_ed25519 is unencrypted on disk. The agent itself must
          # stay — it holds the nixos-anywhere deploy keys, which have no file
          # backing under ~/.ssh and would be destroyed by clearing it.
          settings = {
            default-cache-ttl-ssh = 34560000;
            max-cache-ttl-ssh = 34560000;
          };
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

      # Drop pam_lastlog2 from the login stack: it issues a root-SSD SQLite
      # write on every session open, and its SQLite access has no busy
      # timeout, so concurrent agent session storms fail PAM session setup
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
          services.pueue = {
            enable = true;
            settings.daemon = {
              # One completion callback per task: it appends the finish
              # event to the shared spool (`agentctl events tail`) and
              # notifies the desktop only on failure. Lifecycle events feed
              # the orchestrating agent first; the desktop is a filter.
              callback = "${pkgs.writeShellScript "sinnix-pueue-callback" ''
                set -u
                id=$1 group=$2 result=$3 exit_code=$4 start=$5 end=$6 output_path=$7 queued=$8
                label="$(${pkgs.pueue}/bin/pueue status --json 2>/dev/null \
                  | ${pkgs.jq}/bin/jq -r --arg id "$id" '.tasks[$id].label // empty')"
                ${pkgs.jq}/bin/jq -cn \
                  --arg at "$(${pkgs.coreutils}/bin/date -u +%Y-%m-%dT%H:%M:%S.%6N+00:00)" \
                  --argjson id "$id" --arg group "$group" --arg label "$label" \
                  --arg result "$result" --arg exit_code "$exit_code" \
                  --arg start "$start" --arg end "$end" --arg log "$output_path" \
                  --arg queued "$queued" \
                  '{kind:"queue-task",schema_version:1,emitted_at:$at,task_id:$id,group:$group,
                    label:$label,result:$result,exit_code:$exit_code,started_at:$start,
                    ended_at:$end,log:$log,queued_in_group:$queued}' \
                  >> /realm/state/agentctl/events.jsonl
                if [ "$result" != "Success" ]; then
                  ${pkgs.libnotify}/bin/notify-send -u critical -a pueue \
                    "$group: ''${label:-task $id} $result" "exit $exit_code; pueue log $id" || true
                fi
              ''} {{id}} {{group}} {{result}} {{exit_code}} {{start}} {{end}} {{output_path}} {{queued_count}}";
              callback_log_lines = 0;
            };
          };
          # Worktrees for every repo land under /realm/worktrees as
          # <repo>-<branch>; project hooks live in each repo's .config/wt.toml.
          xdg.configFile."worktrunk/config.toml".text = ''
            worktree-path = "/realm/worktrees/{{ repo }}-{{ branch | sanitize }}"

            [list]
            json-schema = 2

            [remove]
            delete-branch = true
          '';
          systemd.user.services.pueued = {
            # The daemon is only the queue coordinator. Each task's
            # `agentctl-run` child enters the slice named by its declared
            # pool, so pool concurrency and cgroup budgets remain separate.
            Service.Slice = "agentctl-work.slice";
            # state.json carries every task's full client environment; an
            # interactive `pueue add` writes the shell's API keys into it.
            Service.UMask = "0077";
            # A selected verify with eight xdist workers plus testmon fingerprinting
            # exhausted 65,536 descriptors; tasks inherit this limit.
            Service.LimitNOFILE = 524288;
            # A daemon restart marks every running task Killed and pauses
            # groups with queued tasks; a switch must not do that.
            Unit.X-RestartIfChanged = false;
            Unit.X-StopIfChanged = false;
            # Groups live in daemon state, not in the config file.
            Service.ExecStartPost = "${pkgs.writeShellScript "sinnix-pueue-groups" ''
              set -u
              pueue=${pkgs.pueue}/bin/pueue
              for _ in $(seq 1 50); do "$pueue" status >/dev/null 2>&1 && break; sleep 0.2; done
              # One landing slot per project: `agentctl batch land` serializes
              # through <project>-land.
              for spec in agent:8 pytest:1 bulk:1 normal:2 interactive:4 sinnix-land:1 polylogue-land:1 sinex-land:1 lynchpin-land:1; do
                name=''${spec%%:*}; slots=''${spec##*:}
                "$pueue" group add "$name" >/dev/null 2>&1 || true
                "$pueue" parallel -g "$name" "$slots" >/dev/null
              done
            ''}";
          };
          home.packages = lib.mkAfter (
            with pkgs;
            [
              # Agent lanes: worktree lifecycle and the bounded job queue
              # (target architecture 2026-09-02).
              worktrunk
              pueue
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
              # "yes" would import every key ssh touches into gpg-agent's
              # keystore, and gpg-agent will not accept a key without imposing
              # a passphrase on it — one pinentry dialog per new host. ssh
              # reads the unencrypted IdentityFile directly instead; the agent
              # keeps serving the keys already in it.
              "*".AddKeysToAgent = "no";
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
                HostName = "100.111.240.107";
                User = "u0_a460";
                Port = 8022;
                ServerAliveInterval = 30;
              };
            };
          };

          # Desktop -> phone clipboard push. One-way only: Android blocks
          # clipboard READS from a backgrounded app (see the header comment in
          # scripts/sinnix-phone). wl-paste --watch blocks on clipboard change,
          # so this is push-triggered, not a poll loop.
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
            # Home Manager owns ~/.config/broot; the custom skin, modal mode,
            # special paths, and verbs stay in the dots JSON source.
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
