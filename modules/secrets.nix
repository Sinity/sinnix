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
  config,
  ...
}:
let
  username = config.sinnix.user.name;
  primaryGroupName = config.users.users.${username}.group or username;
  userPasswordSecret = "${username}-password";
  # Lives outside the flake checkout entirely (not just gitignored inside
  # it) — encrypted ciphertext + the agenix recipient/inventory manifest
  # shouldn't be at risk from repo-local git operations, and keeping them
  # out of `inputs.self` means they're invisible to Nix's flake-source
  # filtering by construction, not by convention.
  secretDir = /realm/data/secrets/sinnix/secret;
  cfg = config.sinnix.secrets;

  # Auto-discover .age files - evaluated once per flake eval
  secretFiles =
    if cfg.enable && builtins.pathExists secretDir then
      lib.filterAttrs (name: _: lib.hasSuffix ".age" name) (builtins.readDir secretDir)
    else
      { };

  secretNames = lib.mapAttrsToList (name: _: lib.removeSuffix ".age" name) secretFiles;

  # Declarative per-secret overrides. Any secret NOT listed here falls back to
  # the defaults below (owner = username, mode = "0400", exportEnv = true).
  # Add a special-cased secret by adding one attrset entry -- no control flow.
  secretMeta = {
    "github-token" = {
      group = "nixbld";
      mode = "0440";
    };
    "sinex-local-db" = {
      group = if config.users.groups ? postgres then "postgres" else primaryGroupName;
      mode = "0440";
    };
    ${userPasswordSecret} = {
      owner = "root";
      group = "root";
      exportEnv = false;
    };
    "root-password" = {
      owner = "root";
      group = "root";
      exportEnv = false;
    };
    "router-sinnix-prime-mac".exportEnv = false;
    "borg-passphrase".exportEnv = false;
    "configstore-update-notifier".exportEnv = false;
    "factorio-token".exportEnv = false;
    "wifi-psk".exportEnv = false;
  };

  secretSpecs = lib.mapAttrs' (filename: _: {
    name = lib.removeSuffix ".age" filename;
    value =
      let
        secretName = lib.removeSuffix ".age" filename;
        meta = secretMeta.${secretName} or { };
      in
      {
        file = secretDir + "/${filename}";
        path = "/run/agenix/${secretName}";
        owner = meta.owner or username;
        mode = meta.mode or "0400";
      }
      // lib.optionalAttrs (meta ? group) { inherit (meta) group; };
  }) secretFiles;

  mkSecretExport =
    secretName:
    let
      envName = lib.toUpper (lib.replaceStrings [ "-" "." ] [ "_" "_" ] secretName);
      spec = lib.getAttr secretName secretSpecs;
      exportEnv = (secretMeta.${secretName} or { }).exportEnv or true;
    in
    lib.optionalString exportEnv ''
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
