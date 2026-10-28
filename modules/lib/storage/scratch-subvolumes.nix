# Boot provisioning belongs to storage infrastructure, not a scheduled job.
{
  config,
  lib,
  pkgs,
  utils,
  ...
}:
let
  realm = config.sinnix.paths.realmRoot;
  relativePaths = import ./scratch-roots.nix;
  paths = map (path: "${realm}/${path}") relativePaths;
  mountUnit = path: "${utils.escapeSystemdPath path}.mount";
  # Both mounts below the targets and binds sourced from them must wait.
  consumerMounts = lib.filter (
    fs:
    lib.any (
      path:
      fs.mountPoint == path
      || lib.hasPrefix "${path}/" fs.mountPoint
      || fs.device == path
      || lib.hasPrefix "${path}/" fs.device
    ) paths
  ) (builtins.attrValues config.fileSystems);
  migration = pkgs.writeShellApplication {
    name = "realm-scratch-subvolumes";
    runtimeInputs = [
      pkgs.btrfs-progs
      pkgs.coreutils
      pkgs.python3
      pkgs.systemd
    ];
    text = ''
      exec python3 ${./scratch-subvolumes.py} "$@"
    '';
  };
in
{
  systemd.services.realm-scratch-subvolumes =
    lib.mkIf ((config.fileSystems.${realm}.fsType or null) == "btrfs")
      {
        description = "Move regenerable Realm scratch into snapshot-excluded subvolumes";
        wantedBy = [ "local-fs.target" ];
        requires = [ (mountUnit realm) ];
        after = [ (mountUnit realm) ];
        before = [
          "local-fs.target"
          "systemd-tmpfiles-setup.service"
          "realm-scaffold.service"
          "user@${toString config.users.users.${config.sinnix.user.name}.uid}.service"
        ]
        ++ map (fs: mountUnit fs.mountPoint) consumerMounts;
        # Activation must not migrate live worktrees. Boot dependency starts are
        # permitted; manual starts and switch restarts are forbidden.
        restartIfChanged = false;
        unitConfig = {
          DefaultDependencies = false;
          RefuseManualStart = true;
        };
        serviceConfig = {
          Type = "oneshot";
          RemainAfterExit = true;
          ExecStart = "${migration}/bin/realm-scratch-subvolumes --boot-only ${lib.escapeShellArgs paths}";
          # Failure is journal-visible but never blocks boot or login.
          TimeoutStartSec = "infinity";
        };
      };
}
