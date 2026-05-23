# Agenix secret management with auto-discovery
#
# Auto-discovers .age files in secret/ directory and generates:
# - age.secrets entries with appropriate permissions
# - Environment export script for shell integration
# - config.sinnix.secrets.paths for programmatic access
#
# Note: Uses builtins.readDir at eval time for auto-discovery. This adds
# minor eval overhead but eliminates the need for a separate manifest file.
{
  lib,
  inputs,
  config,
  ...
}:
let
  username = config.sinnix.user.name;
  primaryGroupName = config.users.users.${username}.group or username;
  userPasswordSecret = "${username}-password";
  secretDir = inputs.self + "/secret";
  cfg = config.sinnix.secrets;

  # Auto-discover .age files - evaluated once per flake eval
  secretFiles =
    if cfg.enable && builtins.pathExists secretDir then
      lib.filterAttrs (name: _: lib.hasSuffix ".age" name) (builtins.readDir secretDir)
    else
      { };

  secretNames = lib.mapAttrsToList (name: _: lib.removeSuffix ".age" name) secretFiles;

  secretSpecs = lib.mapAttrs' (filename: _: {
    name = lib.removeSuffix ".age" filename;
    value =
      let
        secretName = lib.removeSuffix ".age" filename;
        defaultSpec = {
          owner = username;
          mode = "0400";
        };
        rootOwnedSpec = defaultSpec // {
          owner = "root";
          group = "root";
        };
      in
      {
        file = secretDir + "/${filename}";
      }
      // (
        if secretName == "github-token" then
          defaultSpec
          // {
            group = "nixbld";
            mode = "0440";
            path = "/run/agenix/github-token";
          }
        else if secretName == "sinex-local-db" then
          defaultSpec
          // {
            group = if config.users.groups ? postgres then "postgres" else primaryGroupName;
            mode = "0440";
            path = "/run/agenix/sinex-local-db";
          }
        else if secretName == userPasswordSecret then
          rootOwnedSpec // { path = "/run/agenix/${userPasswordSecret}"; }
        else if secretName == "root-password" then
          rootOwnedSpec // { path = "/run/agenix/root-password"; }
        else
          defaultSpec // { path = "/run/agenix/${secretName}"; }
      );
  }) secretFiles;

  secretsExcludedFromEnv = [
    userPasswordSecret
    "root-password"
    "router-sinnix-prime-mac"
    "borg-passphrase"
    "configstore-update-notifier"
    "factorio-token"
    "wifi-psk"
  ];

  mkSecretExport =
    secretName:
    let
      envName = lib.toUpper (lib.replaceStrings [ "-" "." ] [ "_" "_" ] secretName);
      spec = lib.getAttr secretName secretSpecs;
    in
    lib.optionalString (!lib.elem secretName secretsExcludedFromEnv) ''
      if [[ -r "${spec.path}" ]]; then
        export ${envName}="$(<${spec.path})"
      fi
    '';

  secretsExportScript = lib.concatStringsSep "\n" (
    lib.filter (s: s != "") (map mkSecretExport secretNames)
  );
in
{
  options.sinnix.secrets.enable =
    lib.mkEnableOption "Include agenix-managed secrets and export helpers."
    // {
      default = true;
    };

  options.sinnix.secrets.exportScript = lib.mkOption {
    type = lib.types.str;
    description = "Shell function snippet for exporting decrypted agenix secrets to the environment.";
    default = "";
  };

  options.sinnix.secrets.paths = lib.mkOption {
    type = lib.types.attrsOf lib.types.str;
    description = "Resolved file paths for decrypted secrets managed by agenix.";
    default = { };
  };

  config = {
    # mkForce: Ensure these options are authoritative regardless of module import order
    sinnix.secrets.exportScript = lib.mkForce (if cfg.enable then secretsExportScript else "");
    sinnix.secrets.paths = lib.mkForce (
      if cfg.enable then lib.mapAttrs (_: spec: spec.path) secretSpecs else { }
    );

    age = {
      # With impermanence, /etc/ssh and ~/.ssh are empty at activation time
      # (bind-mounts from /persist haven't run yet). Point directly at /persist
      # paths so agenix can decrypt before bind-mounts complete.
      identityPaths =
        if cfg.enable then
          [
            "/persist/etc/ssh/ssh_host_ed25519_key"
            "/persist/home/${username}/.ssh/id_ed25519"
          ]
        else
          [ ];
      secrets = if cfg.enable then secretSpecs else { };
    };

    # Export decrypted secrets into shells via /etc/profile.d
    environment.etc."profile.d/agenix-secrets.sh" = lib.mkIf (cfg.enable && secretNames != [ ]) {
      mode = "0444";
      text = ''
        # shellcheck shell=bash
        ${secretsExportScript}
      '';
    };

    environment.shellInit = lib.mkIf cfg.enable ''
      if [ -f /etc/profile.d/agenix-secrets.sh ]; then
        # shellcheck disable=SC1091
        . /etc/profile.d/agenix-secrets.sh
      fi
    '';
  };
}
