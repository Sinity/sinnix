# Core Nix Configuration
#
# Platform defaults, documentation policy, security, firewall, and small
# system integration fixes. Nix daemon/build scratch policy lives in
# build-policy.nix.
{
  inputs,
  lib,
  config,
  ...
}:
let
  username = config.sinnix.user.name;
  inherit (config.sinnix) paths;
in
{
  config = {
    nixpkgs = {
      config = {
        allowUnfree = true;
        checkMeta = false;
      };
      hostPlatform = "x86_64-linux";
    };

    documentation.enable = lib.mkDefault false;
    documentation.info.enable = false;
    documentation.nixos.enable = false;
    programs.command-not-found.enable = false;

    services.xserver.xkb.layout = "pl";

    system.activationScripts.githubNetrc = lib.mkIf config.sinnix.secrets.enable ''
      if [ -r ${config.sinnix.secrets.paths."github-token"} ]; then
        token="$(tr -d '\r\n' < ${config.sinnix.secrets.paths."github-token"})"
        install -m 0640 -o root -g nixbld -D /dev/null /etc/nix/netrc
        printf 'machine github.com login x-access-token password %s\n' "$token" > /etc/nix/netrc
        printf 'machine api.github.com login x-access-token password %s\n' "$token" >> /etc/nix/netrc
      else
        rm -f /etc/nix/netrc
      fi
    '';

    system.stateVersion = "24.05";

    security = {
      rtkit.enable = true;
      sudo.wheelNeedsPassword = false;
    };

    networking.firewall = {
      enable = true;
      allowPing = true;
      allowedTCPPorts = [ 22 ];
    };

    systemd = {
      # Boot-started services the desktop does not wait for. A target orders
      # itself after every unit it wants, so a daemon wanted by
      # multi-user.target holds back graphical.target, which the uwsm login
      # gate waits on. This target sets DefaultDependencies=no so it drops
      # that implicit ordering: it activates immediately and its units finish
      # starting in the background.
      targets.sinnix-background = {
        description = "Background services started at boot without gating login";
        wantedBy = [ "multi-user.target" ];
        unitConfig.DefaultDependencies = false;
      };

      tmpfiles.rules = lib.mkAfter [
        "d ${paths.outerRealm} 0755 root root -"
        "d ${paths.outerRealm}/inbox 0755 ${username} users -"
        # The lake is the operator's, like every other root in this list.
        # These two were the outliers at root:root, which meant any capture
        # producer running as the operator could not create its own lane
        # directory: sinnix-census, sinnix-url-ledger and sinnix-video-resolve
        # had each never written a single file while their timers reported
        # success. Root daemons that write here are unaffected -- root ignores
        # directory permissions.
        #
        # tmpfiles `d` also re-owns an existing directory to its declared
        # owner (2026-09-28: four root-owned /realm containers became the
        # operator's at activation with no manual chown), but only for
        # directories with a rule of their own and a safe parent chain.
        # Undeclared directories created root-side (a sudo mkdir, a recut)
        # keep their owner; 2026-08-17 that had re-sprinkled root ownership
        # across /realm, /realm/state, /realm/library, /realm/tmp/work, and
        # five recut subject roots, so those roots are declared below. The
        # list avoids `z`/`Z`: re-chowning live trees every boot is its own
        # hazard. Service-state leaves root daemons own
        # (state/journal, state/containers, backup targets, swap, the
        # snapshots under .btrfs) stay root on purpose.
        #
        # A container directory that only holds such leaves is still the
        # operator's: tmpfiles refuses (as an unsafe path transition) every
        # rule whose parent chain steps from a user-owned directory into a
        # root-owned one, so a root-owned container silently disables every
        # rule beneath it.
        "d ${paths.realmRoot} 0755 ${username} users -"
        "f+ ${paths.realmRoot}/.hidden 0644 ${username} users - state\\ntmp\\nworktree\\n"
        "d ${paths.realmRoot}/.btrfs 0755 ${username} users -"
        "d /realm/state 0755 ${username} users -"
        "d /realm/state/cache 0755 ${username} users -"
        "d /realm/state/cursors 0755 ${username} users -"
        "d /realm/state/db-dumps 0755 ${username} users -"
        "d /realm/tmp/work 0700 ${username} users 30d"
        "d ${paths.realmRoot}/account 0755 ${username} users -"
        "d ${paths.personalRoot} 0700 ${username} users -"
        "d ${paths.devicesRoot} 0755 ${username} users -"
        "d ${config.sinnix.projects.root} 0755 ${username} users -"
        "d ${paths.activityRoot} 0755 ${username} users -"
        "d ${paths.machineRoot} 0775 ${username} users -"
        "d ${paths.healthRoot} 0755 ${username} users -"
        "d ${paths.capturePaths.irc} 0755 ${username} users -"
        "d ${paths.capturePaths.shell} 0755 ${username} users -"
        "d ${paths.capturePaths.shell}/zsh 0700 ${username} users -"
        "d ${paths.journalRoot} 0700 ${username} users -"
        "d ${paths.photosRoot} 0755 ${username} users -"
        "d ${paths.realmRoot}/archive 0755 ${username} users -"
        "d ${paths.realmRoot}/report 0755 ${username} users -"
        "d ${paths.libraryRoot} 0755 ${username} users -"
        "d ${paths.datasetsRoot} 0755 ${username} users -"
        "d ${paths.documentsRoot} 0755 ${username} users -"
        "d ${paths.collectionPaths.account-lastpass} 0755 ${username} users -"
        "d ${paths.collectionPaths.account-lastpass}/raw 0755 ${username} users -"
        "d ${paths.capturePaths.activitywatch} 0755 ${username} users -"
        "d ${paths.capturePaths.activitywatch}/raw 0755 ${username} users -"
        "d ${paths.capturePaths.audio} 0755 ${username} users -"
        "d ${paths.capturePaths.audio}/raw 0755 ${username} users -"
        "d ${paths.capturePaths.audio}/archive 0755 ${username} users -"
        "d ${paths.capturePaths.asciinema} 0755 ${username} users -"
        "d ${paths.capturePaths.keylog} 0700 ${username} users -"
        "d ${paths.capturePaths.screenshot} 0755 ${username} users -"
        "d ${paths.capturePaths.screenshot}/mpv 0755 ${username} users -"
        "d /var/run/nscd 0755 nscd nscd -"
      ];

    };

    # nsncd opens its compatibility socket at /var/run/nscd/socket, but the
    # upstream unit bind-mounts only /run/nscd and leaves /var/run read-only
    # under ProtectSystem=strict — nss-user-lookup.target then fails at boot.
    systemd.services.nscd.serviceConfig.ReadWritePaths = [
      "/run/nscd"
      "/var/run/nscd"
    ];
  };
}
