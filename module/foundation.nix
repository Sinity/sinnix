# Foundation Domain Module
# Core system bootstrap, users, security
# Consolidates: system.nix, user.nix, security.nix

{
  config,
  lib,
  username, # Used in imported modules
  ...
}:
with lib;
{
  imports = [
    # Temporarily import existing modules during migration
    ./system/system.nix
    ./system/user.nix
    ./system/security.nix
    # Note: nix-ld.nix moved to development domain
    # Note: network.nix will go to communication domain
    # Note: services.nix will be split across domains
  ];

  # Foundation configuration will be consolidated here incrementally
  config = {
    # Phase 2 marker - foundation domain active
    system.nixos.tags = [ "foundation-domain-v0.3" ];

    # Username is used by imported modules
    assertions = [
      {
        assertion = username != "";
        message = "Username must be set";
      }
    ];

    # Core systemd configuration (from services.nix)
    systemd.extraConfig = "DefaultTimeoutStopSec=5s";
    systemd.sleep = {
      extraConfig = ''
        AllowSuspend=yes
        AllowHibernation=yes
        AllowSuspendThenHibernate=yes
        AllowHybridSleep=yes
        HibernateMode=reboot
        HibernateState=disk
      '';
    };

    # Journald configuration (from services.nix)
    services.journald = {
      extraConfig = ''
        SystemMaxUse=50G
        SystemKeepFree=25G
        SystemMaxFileSize=10M
        SystemMaxFiles=5000000
        RuntimeMaxUse=2G
      '';
    };
  };
}
