{ lib, ... }:
{
  services.photoprism = {
    enable = true;
    originalsPath = "/realm/data/media";
    importPath = "/realm/data/media/import";
    storagePath = "/realm/data/media/photoprism";
    passwordFile = "/run/agenix/photoprism-admin-password";
    settings = {
      PHOTOPRISM_ADMIN_USER = "sinity";
      PHOTOPRISM_SITE_CAPTION = "Realm Library";
      PHOTOPRISM_DISABLE_FACES = "false";
      PHOTOPRISM_DISABLE_CLASSIFICATION = "false";
    };
  };

  systemd.tmpfiles.rules = lib.mkBefore [
    "d /realm/data/media 0755 sinity users -"
    "d /realm/data/media/import 2770 photoprism users -"
    "d /realm/data/media/photoprism 2770 photoprism photoprism -"
  ];

  users.groups.photoprism = { };

  users.users.photoprism = {
    isSystemUser = true;
    group = "photoprism";
    home = "/var/lib/photoprism";
    extraGroups = [ "users" ];
  };
}
