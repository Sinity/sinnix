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
        # GOTCHA these rules cannot fix: tmpfiles `d` applies ownership only
        # when it CREATES the directory; an existing root-owned dir is left
        # exactly as found (repair semantics belong to `z`, which this list
        # deliberately avoids -- blanket re-chowning live trees every boot is
        # its own hazard). A directory that existed before its rule, or was
        # created root-side (a sudo mkdir, a recut), keeps its wrong owner
        # until someone chowns it once. 2026-08-17: exactly that had
        # re-sprinkled root ownership across /realm, /realm/state,
        # /realm/library, /realm/tmp/{work,shell}, and five recut subject
        # roots; repaired by one-shot chown, and the roots are declared below
        # so new hosts start correct. Service-state dirs root daemons own
        # (state/journal, state/containers, backup targets, swap, .btrfs)
        # stay root on purpose.
        "d ${paths.realmRoot} 0755 ${username} users -"
        "d /realm/state 0755 ${username} users -"
        "d /realm/library 0755 ${username} users -"
        "d /realm/library/datasets 0755 ${username} users -"
        "d /realm/tmp/work 0755 ${username} users -"
        "d /realm/tmp/shell 0755 ${username} users -"
        "d ${paths.dataRoot}/accounts 0755 ${username} users -"
        "d ${paths.dataRoot}/code 0755 ${username} users -"
        "d ${paths.dataRoot}/reports 0755 ${username} users -"
        "d ${paths.dataRoot}/notes 0755 ${username} users -"
        "d ${paths.dataRoot} 0755 ${username} users -"
        "d ${paths.capturesRoot} 0755 ${username} users -"
        "d ${paths.activityRoot} 0755 ${username} users -"
        "d ${paths.machineRoot} 0755 ${username} users -"
        "d ${paths.healthRoot} 0755 ${username} users -"
        "d ${paths.commsRoot} 0755 ${username} users -"
        "d ${paths.commsRoot}/irc 0755 ${username} users -"
        "d ${paths.aiRoot} 0755 ${username} users -"
        "d ${paths.activityRoot}/shell 0755 ${username} users -"
        "d ${paths.activityRoot}/shell/zsh 0700 ${username} users -"
        "d ${paths.exportsRoot} 0755 ${username} users -"
        "d ${paths.selfRoot} 0755 ${username} users -"
        "d ${paths.mediaRoot} 0755 ${username} users -"
        "d ${paths.dataRoot}/records 0755 ${username} users -"
        "d ${paths.dataRoot}/records/lastpass 0755 ${username} users -"
        "d ${paths.dataRoot}/records/lastpass/raw 0755 ${username} users -"
        "d ${paths.activityRoot}/activitywatch 0755 ${username} users -"
        "d ${paths.activityRoot}/activitywatch/activitywatch 0755 ${username} users -"
        "d ${paths.activityRoot}/activitywatch/activitywatch/raw 0755 ${username} users -"
        "d ${paths.activityRoot}/audio 0755 ${username} users -"
        "d ${paths.activityRoot}/audio/raw 0755 ${username} users -"
        "d ${paths.activityRoot}/audio/archive 0755 ${username} users -"
        "d ${paths.activityRoot}/asciinema 0755 ${username} users -"
        "d ${paths.activityRoot}/keylog 0700 ${username} users -"
        "d ${paths.activityRoot}/screenshot 0755 ${username} users -"
        "d ${paths.activityRoot}/screenshot/mpv 0755 ${username} users -"
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
