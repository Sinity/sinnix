{
  lib,
  inputs,
  ...
}:
let
  username = "sinity";
  secretDir = "${inputs.self}/secret";

  secretFiles =
    if builtins.pathExists secretDir then
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
        file = secretDir + "/" + filename;
      }
      // (
        if secretName == "github-token" then
          defaultSpec
          // {
            group = "nixbld";
            mode = "0440";
            path = "/run/agenix/github-token";
          }
        else if secretName == "davfs2-secrets" then
          rootOwnedSpec
          // {
            mode = "0600";
            path = "/run/agenix/davfs2-secrets";
          }
        else if secretName == "photoprism-admin-password" then
          rootOwnedSpec // { path = "/run/agenix/photoprism-admin-password"; }
        else if secretName == "sinity-password" then
          rootOwnedSpec // { path = "/run/agenix/sinity-password"; }
        else if secretName == "root-password" then
          rootOwnedSpec // { path = "/run/agenix/root-password"; }
        else
          defaultSpec // { path = "/run/agenix/${secretName}"; }
      );
  }) secretFiles;

  secretsExcludedFromEnv = [
    "sinity-password"
    "root-password"
    "davfs2-secrets"
    "photoprism-admin-password"
    "configstore-update-notifier"
    "gcloud-config.tar.gz"
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
  options.sinnix.secrets.exportScript = lib.mkOption {
    type = lib.types.str;
    description = "Shell function snippet for exporting decrypted agenix secrets to the environment.";
    readOnly = true;
  };

  options.sinnix.secrets.paths = lib.mkOption {
    type = lib.types.attrsOf lib.types.str;
    description = "Resolved file paths for decrypted secrets managed by agenix.";
    readOnly = true;
  };

  config = {
    sinnix.secrets.exportScript = secretsExportScript;
    sinnix.secrets.paths = lib.mapAttrs (_: spec: spec.path) secretSpecs;

    age = {
      identityPaths = [
        "/etc/ssh/ssh_host_ed25519_key"
      ]
      ++ lib.optionals (builtins.pathExists "/home/${username}/.ssh/id_ed25519") [
        "/home/${username}/.ssh/id_ed25519"
      ];

      secrets = secretSpecs;
    };
  };
}
