# Domain Module Factory
# Provides consistent structure for all domain modules with v0.5 extension points

{ lib }:
with lib;

{
  # Create a domain module with standard structure
  mkDomainModule =
    {
      name,
      description ? "Domain module for ${name}",
      systemConfig ? { },
      userConfig ? { },
      options ? { },
    }:
    {
      config,
      username,
      ...
    }:
    let
      cfg = config.services.${name};
      # Sinity alias pattern - define this in your domain modules:
      # sinity = config.home-manager.users.${username};
    in
    {
      options.services.${name} = {
        enable = mkEnableOption "${name} domain configuration";

        # v0.5 Extension Points
        extraSystemConfig = mkOption {
          type = types.attrs;
          default = { };
          description = "Additional system configuration for ${name} services";
        };

        extraUserConfig = mkOption {
          type = types.attrs;
          default = { };
          description = "Additional user configuration for ${name} services";
        };

        stateDir = mkOption {
          type = types.path;
          default = "/var/lib/${name}";
          description = "State directory for ${name} services";
        };

        # Custom options for this domain
      } // options;

      config = mkIf cfg.enable (mkMerge [
        # Core system configuration
        systemConfig

        # User configuration via home-manager
        {
          home-manager.users.${username} = mkMerge [
            userConfig
            cfg.extraUserConfig
          ];
        }

        # v0.5 service extensions
        cfg.extraSystemConfig

        # Ensure state directory exists
        {
          systemd.tmpfiles.rules = [
            "d ${cfg.stateDir} 0755 ${username} users -"
          ];
        }
      ]);
    };
}
