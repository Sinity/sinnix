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
      userRuntimeDirectory = "/run/user/${toString config.users.users.${user}.uid}";
    in
    lib.mkMerge [
      # Worktrees are removed when their work is in the default branch, not
      # when someone notices them. agentctl removes only the worktrees its
      # landing step finishes, and Claude Code, forks and hand-made trees
      # have no removal at all: 500+ piled up once and 184 on 2026-10-19,
      # each needing a manual triage. Daily, for every project repository:
      # `wt step prune` removes worktrees and branches whose changes are in
      # the default branch (squash merges included) and skips dirty, locked
      # and day-old ones; worktrees a live process is inside are locked for
      # the run so they are never pulled out from under a session. Separately,
      # directories under /realm/worktree without a .git are leftovers of an
      # interrupted removal and are deleted. Unmerged worktrees untouched for
      # 14 days stay (they hold commits nowhere else), and are announced.
      (lib.sinnix.mkScheduledJob
        {
          inherit config;
          unitName = "sinnix-worktree-reap";
          description = "Remove merged and orphaned worktrees";
        }
        {
          manager = "user";
          resourceClass = "background";
          path = [
            pkgs.coreutils
            pkgs.findutils
            pkgs.git
            pkgs.gnugrep
            pkgs.libnotify
            pkgs.worktrunk
          ];
          serviceConfig.TimeoutStartSec = "1h";
          script = ''
            set -uo pipefail
            # Every directory a live process works in, read once.
            held=$(for proc in /proc/[0-9]*; do readlink "$proc/cwd" 2>/dev/null; done | sort -u)
            in_use() {
              printf '%s\n' "$held" | grep -qxF -e "$1" || printf '%s\n' "$held" | grep -qF -e "$1/"
            }

            locked=()
            unlock_all() {
              for entry in "''${locked[@]}"; do
                git -C "''${entry%%|*}" worktree unlock "''${entry#*|}" 2>/dev/null
              done
              locked=()
            }
            trap unlock_all EXIT

            failed=0
            stale=()
            for repo in /realm/project/*/repo; do
              [ -e "$repo/.git" ] || continue
              # Claude Code locks the worktrees it creates for a session
              # ("claude agent <name> (pid P start S)") and leaves the lock
              # when the session ends; a lock whose process is gone would keep
              # its worktree from ever being pruned.
              git -C "$repo" worktree list --porcelain | awk '/^worktree /{w=substr($0,10)} /^locked claude agent /{print w "\t" $0}' |
                while IFS=$'\t' read -r tree reason; do
                  if [[ $reason =~ \(pid\ ([0-9]+)\ start\ ([0-9]+)\) ]]; then
                    pid=''${BASH_REMATCH[1]} start=''${BASH_REMATCH[2]}
                    now=$(cut -d' ' -f22 "/proc/$pid/stat" 2>/dev/null)
                    if [ "$now" != "$start" ]; then
                      echo "release stale Claude lock: $tree"
                      git -C "$repo" worktree unlock "$tree"
                    fi
                  fi
                done
              while IFS= read -r line; do
                tree=''${line#worktree }
                [ "$tree" = "$repo" ] && continue
                if in_use "$tree" && git -C "$repo" worktree lock --reason "in use during sinnix-worktree-reap" "$tree" 2>/dev/null; then
                  locked+=("$repo|$tree")
                fi
              done < <(git -C "$repo" worktree list --porcelain | grep '^worktree ')
              echo "prune: $repo"
              wt -C "$repo" step prune --yes --foreground --min-age 1d || failed=1
              unlock_all
              # What is left and untouched for two weeks holds unmerged work.
              while IFS= read -r line; do
                tree=''${line#worktree }
                [ "$tree" = "$repo" ] && continue
                [ -d "$tree" ] || continue
                if [ -z "$(find "$tree" -maxdepth 2 -newermt '-14 days' -print -quit 2>/dev/null)" ]; then
                  stale+=("$tree")
                fi
              done < <(git -C "$repo" worktree list --porcelain | grep '^worktree ')
            done

            # A live worktree always carries .git (file or dir); Git never
            # removes the directory itself, so a .git-less entry is residue.
            for d in /realm/worktree/*; do
              [ -d "$d" ] && [ ! -e "$d/.git" ] || continue
              if in_use "$d"; then
                echo "skip (in use): $d"
                continue
              fi
              echo "reaping: $d"
              # Verification receipts are written 0o444 and archive templates
              # read-only; without this the removal fails partway.
              chmod -R u+w "$d" 2>/dev/null || true
              rm -rf "$d"
            done

            if [ "''${#stale[@]}" -gt 0 ]; then
              printf 'unmerged, untouched for 14 days: %s\n' "''${stale[@]}"
              notify-send --app-name=sinnix "Worktrees" \
                "''${#stale[@]} unmerged worktrees untouched for 14 days (journalctl --user -u sinnix-worktree-reap)" || true
            fi
            exit "$failed"
          '';
          timer = {
            onCalendar = "*-*-* 04:00:00";
            persistent = true;
            randomizedDelaySec = "20min";
            accuracySec = "5min";
            description = "Daily merged and orphaned worktree removal";
          };
        }
      )
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
          # `sinnix` -- discoverable entry point over the whole packaged script
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
            # Lifecycle events come from `agentctl-run` alone (started and
            # finished `queue-task` records in the shared spool); pueue runs
            # no completion callback.
            services.pueue = {
              enable = true;
              # System services running as this user do not inherit XDG_RUNTIME_DIR.
              settings.shared.runtime_directory = userRuntimeDirectory;
            };
            # Worktrees for every repo land under /realm/worktree as
            # <repo>-<branch>; project hooks live in each repo's .config/wt.toml.
            xdg.configFile."worktrunk/config.toml".text = ''
              worktree-path = "/realm/worktree/{{ repo }}-{{ branch | sanitize }}"

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
              # Groups live in daemon state, not in the config file:
              # agentctl-pools.service applies the declared parallelism to this
              # daemon whenever it starts and whenever the declaration changes.
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
              config.global = {
                warn_timeout = "30s";
              };
              config.whitelist.prefix = [ "/" ];
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
      }
    ];
} args
