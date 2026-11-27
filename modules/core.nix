# Core Nix Configuration
#
# Platform defaults, documentation policy, security, firewall, and small
# system integration fixes. Nix daemon/build scratch policy lives in
# build-policy.nix.
{
  inputs,
  lib,
  config,
  pkgs,
  ...
}:
let
  username = config.sinnix.user.name;
  inherit (config.sinnix) paths;

  # The managed TMPDIR has /tmp semantics: a temporary file belongs to the
  # process that made it, and a boot ends every process. Before any user
  # session starts, every top-level entry moves aside, except claude-<uid>,
  # whose session trees sinnix-tmp-sweep retires by session (docs/scratch.md).
  # Renaming within one filesystem is instant, so login does not wait for
  # deletion; the set-aside directory is deleted afterwards at idle I/O.
  userUid =
    let
      uid = config.users.users.${username}.uid or null;
    in
    if uid != null then toString uid else "1000";
  scratchRoot = "/realm/tmp/work";
  previousBoot = "/realm/tmp/previous-boot";
  scratchReset = pkgs.writeShellScript "sinnix-scratch-reset" ''
    set -euo pipefail
    shopt -s dotglob nullglob
    ${pkgs.coreutils}/bin/mkdir -p -m 0700 ${previousBoot}
    for entry in ${scratchRoot}/*; do
      name="''${entry##*/}"
      [[ "$name" =~ ^claude-[0-9]+$ ]] && [ -d "$entry" ] && [ ! -L "$entry" ] && continue
      target="${previousBoot}/$name"
      # An interrupted earlier purge can leave the same name behind.
      [ -e "$target" ] || [ -L "$target" ] && target="$(${pkgs.coreutils}/bin/mktemp -u "$target.XXXXXX")"
      ${pkgs.coreutils}/bin/mv -T -- "$entry" "$target"
    done
  '';
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

      services.sinnix-scratch-reset = {
        description = "Set aside the previous boot's managed scratch";
        wantedBy = [ "multi-user.target" ];
        before = [
          "systemd-user-sessions.service"
          "user-runtime-dir@${userUid}.service"
          "user@${userUid}.service"
        ];
        after = [ "systemd-tmpfiles-setup.service" ];
        unitConfig = {
          RequiresMountsFor = [ scratchRoot ];
          # Only a boot, before the owner has any session, qualifies; an
          # activation on the running system starts this unit and skips it.
          ConditionPathExists = "!/run/user/${userUid}";
        };
        restartIfChanged = false;
        serviceConfig = {
          Type = "oneshot";
          ExecStart = scratchReset;
          # A root-run tool that removes files keeps a narrowed write scope.
          ProtectSystem = "strict";
          ReadWritePaths = [ "/realm/tmp" ];
        };
      };

      services.sinnix-scratch-purge = {
        description = "Delete the previous boot's managed scratch";
        wantedBy = [ "sinnix-background.target" ];
        after = [ "sinnix-scratch-reset.service" ];
        unitConfig = {
          RequiresMountsFor = [ "/realm/tmp" ];
          ConditionPathExists = previousBoot;
        };
        restartIfChanged = false;
        serviceConfig = {
          Type = "oneshot";
          ExecStart = "${pkgs.coreutils}/bin/rm -rf --one-file-system -- ${previousBoot}";
          IOSchedulingClass = "idle";
          Nice = 19;
          ProtectSystem = "strict";
          ReadWritePaths = [ "/realm/tmp" ];
        };
      };

      tmpfiles.rules = lib.mkAfter [
        "d ${paths.outerRealm} 0755 root root -"
        "d ${paths.outerRealm}/inbox 0755 ${username} users -"
        # Operator-owned private roots let capture producers create directories;
        # tmpfiles rules need a safe parent chain, without recursive ownership changes.
        "d ${paths.realmRoot} 0700 ${username} users -"
        "f+ ${paths.realmRoot}/.hidden 0644 ${username} users - state\\ntmp\\nworktree\\n"
        "d ${paths.realmRoot}/.btrfs 0755 ${username} users -"
        "d /realm/state 0755 ${username} users -"
        "v /realm/state/cache 0755 ${username} users -"
        "d /realm/state/cursors 0755 ${username} users -"
        "d /realm/state/db-dumps 0755 ${username} users -"
        # Scratch owners decide removal; age alone does not establish
        # disposability. A boot ends every owner (sinnix-scratch-reset above).
        "v /realm/tmp - ${username} - -"
        "d /realm/tmp/work 0700 ${username} users -"
        # Worktrunk can create checkouts before AgentCTL; enforce their shared
        # private path regardless of the first producer's umask.
        "v /realm/worktree 0700 ${username} users -"
        "d ${paths.realmRoot}/account 0700 ${username} users -"
        "d ${paths.personalRoot} 0700 ${username} users -"
        # Correct private note container ownership without recursively changing retained evidence.
        "d ${paths.personalRoot}/idea 0700 ${username} users -"
        "d ${paths.personalRoot}/self-model 0700 ${username} users -"
        "d ${paths.personalRoot}/history/retired-note-system 0700 ${username} users -"
        "d ${paths.devicesRoot} 0755 ${username} users -"
        "d ${config.sinnix.projects.root} 0755 ${username} users -"
        "d ${paths.activityRoot} 0755 ${username} users -"
        "d ${paths.activityRoot}/shared/ranking 0700 ${username} ${config.users.users.${username}.group} -"
        "d ${paths.machineRoot} 0775 ${username} users -"
        "d ${paths.healthRoot} 0700 ${username} users -"
        "d ${paths.capturePaths.irc} 0700 ${username} users -"
        "d ${paths.capturePaths.shell} 0700 ${username} users -"
        "d ${paths.capturePaths.shell}/zsh 0700 ${username} users -"
        "d ${paths.journalRoot} 0700 ${username} users -"
        "d ${paths.photosRoot} 0755 ${username} users -"
        "d ${paths.realmRoot}/archive 0755 ${username} users -"
        "d ${paths.realmRoot}/report 0755 ${username} users -"
        "d ${paths.libraryRoot} 0755 ${username} users -"
        "d ${paths.datasetsRoot} 0755 ${username} users -"
        "d ${paths.documentsRoot} 0700 ${username} users -"
        "d ${paths.collectionPaths.account-lastpass} 0700 ${username} users -"
        "d ${paths.collectionPaths.account-lastpass}/raw 0700 ${username} users -"
        "d ${paths.capturePaths.activitywatch} 0700 ${username} users -"
        "d ${paths.capturePaths.activitywatch}/raw 0700 ${username} users -"
        "d ${paths.capturePaths.audio} 0700 ${username} users -"
        "d ${paths.capturePaths.audio}/raw 0700 ${username} users -"
        "d ${paths.capturePaths.audio}/archive 0700 ${username} users -"
        "d ${paths.capturePaths.asciinema} 0700 ${username} users -"
        "d ${paths.capturePaths.keylog} 0700 ${username} users -"
        "d ${paths.capturePaths.screenshot} 0700 ${username} users -"
        "d ${paths.capturePaths.screenshot}/mpv 0700 ${username} users -"
        "d /var/run/nscd 0755 nscd nscd -"
      ];

    };

    # Files the operator's units, terminals and agents create are private to
    # the operator. User units inherit the user manager's umask, and the
    # manager takes it from this unit.
    systemd.services."user@".serviceConfig.UMask = "0077";

    # nsncd opens its compatibility socket at /var/run/nscd/socket, but the
    # upstream unit bind-mounts only /run/nscd and leaves /var/run read-only
    # under ProtectSystem=strict — nss-user-lookup.target then fails at boot.
    systemd.services.nscd.serviceConfig.ReadWritePaths = [
      "/run/nscd"
      "/var/run/nscd"
    ];
  };
}
