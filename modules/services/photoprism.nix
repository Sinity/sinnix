{ lib, username, ... }:
let
  dataRoot = "/realm/data";
  mediaDir = "${dataRoot}/media";
in
{
  services.photoprism = {
    enable = true;
    originalsPath = mediaDir;
    importPath = "${mediaDir}/import";
    storagePath = "${mediaDir}/photoprism";
    passwordFile = "/run/agenix/photoprism-admin-password";
    settings = {
      PHOTOPRISM_ADMIN_USER = username;
      PHOTOPRISM_SITE_CAPTION = "Realm Library";
      PHOTOPRISM_DISABLE_FACES = "false";
      PHOTOPRISM_DISABLE_CLASSIFICATION = "false";
    };
  };

  systemd.tmpfiles.rules = lib.mkBefore [
    "d ${mediaDir} 0750 ${username} media -"
    "d ${mediaDir}/import 2770 photoprism media -"
    "d ${mediaDir}/photoprism 2770 photoprism media -"
  ];

  users.groups.media = {
    members = [
      username
      "photoprism"
    ];
  };

  users.groups.photoprism = { };

  users.users.photoprism = {
    isSystemUser = true;
    group = "photoprism";
    home = "/var/lib/photoprism";
    extraGroups = [ "media" ];
  };

  systemd.services.photoprism.serviceConfig.LoadCredential = lib.mkForce [
    "PHOTOPRISM_ADMIN_PASSWORD_FILE:/run/agenix/photoprism-admin-password"
  ];
}
