# Agenix secret management with auto-discovery
#
# Auto-discovers .age files (via builtins.readDir at eval time, so no separate
# manifest) and generates age.secrets entries with appropriate permissions, an
# environment export script, and config.sinnix.secrets.paths.
{
  lib,
  config,
  ...
}:
let
  username = config.sinnix.user.name;
  primaryGroupName = config.users.users.${username}.group or username;
  userPasswordSecret = "${username}-password";
  # Outside the flake checkout entirely, not merely gitignored: ciphertext and
  # the agenix recipient manifest stay clear of repo-local git operations and
  # are invisible to Nix's flake-source filtering by construction.
  secretDir = /realm/data/secrets/sinnix/secret;
  cfg = config.sinnix.secrets;

  secretFiles =
    if cfg.enable && builtins.pathExists secretDir then
      lib.filterAttrs (name: _: lib.hasSuffix ".age" name) (builtins.readDir secretDir)
    else
      { };

  secretNames = lib.mapAttrsToList (name: _: lib.removeSuffix ".age" name) secretFiles;

  # Public runtime contracts referenced by this configuration. Listing a name
  # here only makes its conventional /run/agenix path available during pure
  # evaluation; it does not declare a secret or assert that ciphertext exists.
  runtimeSecretContracts = [
    "assemblyai-api-key"
    "cohere-api-key"
    "deepgram-api-key"
    "firecrawl-api-key"
    "openai-api-key"
    "openai-tunnel-runtime-key"
    "sinex-api-admin-token"
    "sinex-nats-ca"
    "sinex-nats-client-nkey"
    "sinex-nats-server-cert"
    "sinex-nats-server-key"
    # Minted by `sinnix spotify-auth` (one interactive browser-authorized
    # bootstrap), not shipped as ciphertext. Declaring the contract here lets
    # capture-spotify.nix reference config.sinnix.secrets.paths.<name> and
    # stay enabled before the token exists -- the unit itself fails loudly
    # with a one-line instruction until the operator runs the auth flow and
    # `agenix -e secret/spotify-refresh-token.age`s the printed value in.
    "spotify-refresh-token"
    # Shared by capture-mail (mbsync IMAP) and capture-calendar (vdirsyncer
    # CalDAV) -- same account, one app-specific password, one agenix secret.
    # Neither module ships ciphertext; both stay default-off until the
    # operator creates this secret (see each module's header).
    "mail-app-password"
  ];

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
    # NATS reads its listener key directly; Sinexd reads the client seed and
    # trust anchor. Keep each runtime credential available only to its owning
    # service account and never export it into login shells.
    "sinex-nats-server-cert" = {
      owner = "nats";
      group = "nats";
      mode = "0440";
      exportEnv = false;
    };
    "sinex-nats-server-key" = {
      owner = "nats";
      group = "nats";
      mode = "0400";
      exportEnv = false;
    };
    "sinex-nats-ca" = {
      owner = "sinex";
      group = "sinex";
      mode = "0440";
      exportEnv = false;
    };
    "sinex-nats-client-nkey" = {
      owner = "sinex";
      group = "sinex";
      mode = "0400";
      exportEnv = false;
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
    "pypi-recovery-codes".exportEnv = false;
    # Exporting this to every shell silently overrides Claude Code's
    # subscription auth for every `claude`/`claude -p` invocation on the host.
    # Nothing here reads ANTHROPIC_API_KEY from the environment; it remains
    # readable at /run/agenix/anthropic-api-key for anything that wants it.
    "anthropic-api-key".exportEnv = false;
    # Account-linked bearer credentials, read directly from /run/agenix by
    # their owning capture lane -- no reason to widen their blast radius to
    # every login shell.
    "spotify-refresh-token".exportEnv = false;
    "mail-app-password".exportEnv = false;
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

  # Consumers need stable runtime paths during pure public evaluation, where
  # Nix deliberately cannot inspect the external ciphertext directory. The
  # actual age.secrets declarations remain limited to files discovered during
  # an impure/live evaluation.
  declaredSecretNames = lib.unique (
    secretNames ++ runtimeSecretContracts ++ builtins.attrNames secretMeta
  );
  secretPaths = lib.genAttrs declaredSecretNames (name: "/run/agenix/${name}");

  mkSecretExport =
    secretName:
    let
      envName = lib.toUpper (lib.replaceStrings [ "-" "." ] [ "_" "_" ] secretName);
      exportEnv = (secretMeta.${secretName} or { }).exportEnv or true;
    in
    lib.optionalString exportEnv ''
      if [[ -r "${secretPaths.${secretName}}" ]]; then
        export ${envName}="$(<${secretPaths.${secretName}})"
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
    sinnix.secrets.paths = lib.mkForce (if cfg.enable then secretPaths else { });

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
