{
  lib,
  username,
  config,
  flakeRoot,
  ...
}:
let
  secretDir = builtins.toString flakeRoot + "/secret";

  secretFiles =
    if builtins.pathExists secretDir then
      lib.filterAttrs (name: _: lib.hasSuffix ".age" name) (builtins.readDir secretDir)
    else
      { };

  secretNames = lib.mapAttrsToList (name: _: lib.removeSuffix ".age" name) secretFiles;

  secretsExcludedFromEnv = [
    "sinity-password"
    "root-password"
    "davfs2-secrets"
    "photoprism-admin-password"
  ];

  mkSecretExport =
    secretName:
    let
      envName = lib.toUpper (lib.replaceStrings [ "-" ] [ "_" ] secretName);
    in
    lib.optionalString (!lib.elem secretName secretsExcludedFromEnv) ''
      if [[ -r "${config.age.secrets.${secretName}.path}" ]]; then
        export ${envName}="$(<${config.age.secrets.${secretName}.path})"
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

  config = {
    sinnix.secrets.exportScript = secretsExportScript;

    age = {
      identityPaths = [
        "/etc/ssh/ssh_host_ed25519_key"
      ]
      ++ lib.optionals (builtins.pathExists "/home/${username}/.ssh/id_ed25519") [
        "/home/${username}/.ssh/id_ed25519"
      ];

      secrets = lib.mapAttrs' (filename: _: {
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
            if secretName == "davfs2-secrets" then
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
    };
  };
}
