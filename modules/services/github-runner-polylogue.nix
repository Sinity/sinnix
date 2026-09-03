# GitHub Actions self-hosted runner for Polylogue's required `verify` check.
#
# The runner is an orchestrator, not the workload. `devtools verify` submits
# pytest to the host's single `pytest` pueue group
# (polylogue devtools/pytest_slot.py), so the heavy phase executes under the
# user-side job plane and inherits its memory ceiling. Reaching that queue is
# why the unit runs as the workstation user with the user manager's runtime
# directory and home in scope; without them `pueue add` cannot find the
# daemon socket and verify refuses rather than running unbounded.
#
# The unit is registered non-ephemeral so its work directory -- git objects,
# the testmon datafile, the devshell venv -- survives between workflow runs.
# Upstream clears the work directory on every service start, not every job.
{
  mkServiceModule,
  config,
  lib,
  pkgs,
  ...
}@args:
let
  userName = config.sinnix.user.name;
  tokenSecret = "github-runner-polylogue-token";
  # Fail closed. modules/secrets.nix declares an age.secrets entry only for
  # ciphertext that exists, so an unminted token leaves the runner off and the
  # host configuration still evaluates and builds.
  tokenAvailable = config.age.secrets ? ${tokenSecret};
in
mkServiceModule {
  name = "github-runner-polylogue";
  description = "GitHub Actions self-hosted runner for the Polylogue verify check";
  extraOptions = {
    url = lib.mkOption {
      type = lib.types.str;
      default = "https://github.com/Sinity/polylogue";
      description = "Repository the runner registers against.";
    };
    workDir = lib.mkOption {
      type = lib.types.str;
      default = "${config.sinnix.paths.stateRoot}/github-runner/polylogue";
      apply =
        path:
        if lib.hasPrefix "/" path then
          path
        else
          throw "sinnix.services.github-runner-polylogue.workDir must be absolute";
      description = ''
        Persistent runner work directory. Must live on NVMe rather than the
        systemd runtime directory: a full Polylogue checkout plus its devshell
        venv does not belong in a tmpfs.
      '';
    };
    labels = lib.mkOption {
      type = lib.types.listOf lib.types.str;
      default = [ "sinnix-prime" ];
      description = "Host labels workflows select this runner with.";
    };
  };
  configFn =
    { cfg, ... }:
    lib.mkMerge [
      {
        warnings = lib.optional (!tokenAvailable) ''
          sinnix.services.github-runner-polylogue is enabled but the agenix
          secret ${tokenSecret} does not exist, so the runner is not
          configured. Mint the token and encrypt it to
          secret/${tokenSecret}.age to activate it.
        '';
      }
      (lib.mkIf tokenAvailable {
        sinnix.runtime.surfaces.github-runner-polylogue = {
          unit = "github-runner-polylogue.service";
          resourceClass = "managed-runtime-work";
          observe = {
            enable = true;
            restartable = true;
          };
          workload = {
            class = "sacrificial";
            rationale = "CI runner; a killed run is retried by GitHub.";
            processMatchers = [ "Runner.Listener" ];
          };
        };

        systemd.tmpfiles.rules = [
          "d ${builtins.dirOf cfg.workDir} 0755 ${userName} users -"
          "d ${cfg.workDir} 0755 ${userName} users -"
        ];

        services.github-runners.polylogue = {
          enable = true;
          inherit (cfg) url workDir;
          # Long-lived registration: the work directory is the cache that makes
          # a selected verify run cheap, and ephemeral mode discards it.
          ephemeral = false;
          replace = true;
          name = config.networking.hostName;
          extraLabels = cfg.labels;
          user = userName;
          group = config.users.users.${userName}.group;
          tokenFile = config.sinnix.secrets.paths.${tokenSecret};

          # `nix develop` provides the rest; these are what the runner itself
          # and the checkout/artifact actions need on PATH.
          extraPackages = with pkgs; [
            # devtools submits pytest to the user pueue slot from inside
            # `nix develop`, which inherits this PATH.
            pueue
            uv
            cacert
            openssh
            curl
            jq
            xz
            gawk
            gnused
            gnugrep
            findutils
          ];

          extraEnvironment = {
            # The pueue client resolves its socket and configuration from
            # these two. Specifiers would name the manager's user (root), not
            # User=, so the paths are literal.
            HOME = "/home/${userName}";
            XDG_RUNTIME_DIR = "/run/user/${toString config.users.users.${userName}.uid}";
            # The unit starts outside any login session and outside the user
            # manager, so it inherits neither place's TMPDIR. Without this the
            # workflow's `nix develop` puts its scratch tree, and the seeded
            # archives of every xdist worker, on the 6 GiB /tmp tmpfs.
            TMPDIR = "/realm/tmp/${userName}";
            SSL_CERT_FILE = "/etc/ssl/certs/ca-certificates.crt";
            NIX_SSL_CERT_FILE = "/etc/ssl/certs/ca-certificates.crt";
          };

          serviceOverrides = {
            # The job plane's slice. The ceiling that matters is the one the
            # pueue task inherits; this placement governs CPU and IO weight.
            Slice = "sinnixd-work.slice";
            # A selected verify opens the seeded archives of every xdist worker at
            # once; the default 1024 gave EMFILE on the first real run.
            LimitNOFILE = 65536;

            DynamicUser = false;
            # A CI runner needs the user's caches, the nix daemon socket, the
            # checkout under /realm, and unrestricted /tmp. Upstream's default
            # hardening assumes an isolated build user and denies all four.
            ProtectHome = false;
            ProtectSystem = false;
            PrivateTmp = false;
            PrivateUsers = false;
            PrivateDevices = false;
            PrivateMounts = false;
            ProtectControlGroups = false;
            RestrictNamespaces = false;
            ProtectProc = "default";

            # Upstream fixes this to "no" for non-ephemeral runners; a listener
            # that dies on a network blip would otherwise stay down silently.
            Restart = lib.mkForce "always";
            RestartSec = "30s";
          };
        };
      })
    ];
} args
