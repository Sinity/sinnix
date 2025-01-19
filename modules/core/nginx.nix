{ config, pkgs, ... }:
{
  # Enable NGINX
  services.nginx = {
    enable = true;
    
    virtualHosts."_" = {
      listen = [{ addr = "0.0.0.0"; port = 80; }];
      root = "/var/www/simple-site";
    };
  };

  # Create the web directory with appropriate permissions
  system.activationScripts = {
    createWebDir = {
      text = ''
        mkdir -p /var/www/simple-site
        chown -R nginx:nginx /var/www/simple-site
      '';
      deps = [];
    };
  };
}
