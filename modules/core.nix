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

    # Record the flake commit that produced this generation. Surfaces via
    # `nixos-version --revision` and is read at activation time by the
    # lynchpin generation-log script so substrate can join telemetry rows
    # back to the sinnix git history. Falls through to "dirty"/"unknown"
    # if the source tree was uncommitted at build time, which is itself
    # diagnostically useful (rebuilds from local edits are visible).
    system.configurationRevision = inputs.self.rev or inputs.self.dirtyRev or "unknown";

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
        "d ${paths.realmRoot} 0755 root root -"
        "d ${paths.outerRealm} 0755 root root -"
        "d ${paths.outerRealm}/inbox 0755 ${username} users -"
        "d ${paths.dataRoot} 0755 root root -"
        "d ${paths.capturesRoot} 0755 root root -"
        "d ${paths.capturesRoot}/shell 0755 ${username} users -"
        "d ${paths.capturesRoot}/shell/zsh 0700 ${username} users -"
        "d ${paths.capturesRoot}/comms 0755 ${username} users -"
        "d ${paths.capturesRoot}/comms/irc 0755 ${username} users -"
        "d ${paths.exportsRoot} 0755 ${username} users -"
        "d ${paths.librariesRoot} 0755 ${username} users -"
        "d ${paths.capturesRoot}/activitywatch 0755 ${username} users -"
        "d ${paths.capturesRoot}/activitywatch/raw 0755 ${username} users -"
        "d ${paths.capturesRoot}/audio 0755 ${username} users -"
        "d ${paths.capturesRoot}/audio/raw 0755 ${username} users -"
        "d ${paths.capturesRoot}/audio/archive 0755 ${username} users -"
        "d ${paths.capturesRoot}/asciinema 0755 ${username} users -"
        "d ${paths.capturesRoot}/keylog 0700 ${username} users -"
        "d ${paths.capturesRoot}/screenshot 0755 ${username} users -"
        "d ${paths.capturesRoot}/screenshot/mpv 0755 ${username} users -"
        "d ${paths.exportsRoot}/lastpass 0755 ${username} users -"
        "d ${paths.exportsRoot}/lastpass/raw 0755 ${username} users -"
        "d /var/run/nscd 0755 nscd nscd -"
      ];

    };

    services.dbus.implementation = "broker";
    # NOTE: dbus-broker hardening removed - it needs setgroups() to drop privileges
    # for spawned services. The ~@privileged syscall filter blocked this, causing
    # crashes at boot. See: journalctl -b -3 | grep dbus-broker
    # User dbus-broker reloads have timed out during switch activation after
    # inotify ENOSPC bursts. Keep the live session bus stable; unit changes can
    # take effect on the next login instead of failing the whole deployment.
    systemd.user.services.dbus-broker = {
      reloadIfChanged = lib.mkForce false;
      restartIfChanged = lib.mkForce false;
      stopIfChanged = lib.mkForce false;
    };

    # nsncd opens its compatibility socket at /var/run/nscd/socket. On the
    # current systemd/nixpkgs generation the upstream unit bind-mounts /run/nscd
    # but still leaves the /var/run path read-only under ProtectSystem=strict,
    # causing nss-user-lookup.target to fail repeatedly during boot.
    systemd.services.nscd.serviceConfig.ReadWritePaths = [
      "/run/nscd"
      "/var/run/nscd"
    ];
  };
}
