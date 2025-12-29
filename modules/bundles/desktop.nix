{ lib, config, ... }:
let
  cfg = config.sinnix.bundles.desktop;
in
{
  options.sinnix.bundles.desktop = {
    enable = lib.mkEnableOption "Standard Desktop Environment Bundle";
  };

  config = lib.mkIf cfg.enable {
    sinnix = {
      machine.isDesktop = true;
      
      # Enable core desktop capabilities
      ui.enable = true;
      audio.enable = true;
      programs.nix-ld.enable = true;
      features.desktop.hyprland.enable = true;
      features.desktop.terminal.enable = true;
      features.desktop.waybar.enable = true;
      features.desktop.tofi.enable = true;
      features.desktop.fnott.enable = true;
      features.desktop.clipse.enable = true;
      features.desktop.common-apps.enable = true;
      features.desktop.crypto.enable = true;
      features.desktop.media.enable = true;
      features.desktop.browser.enable = true;
      features.desktop.storage.enable = true;
      features.desktop.wayland-session.enable = true;
      features.desktop.background-services.enable = true;
      features.desktop.activitywatch.enable = true;
      features.desktop.kdeconnect.enable = true;
      features.desktop.reboot-notifier.enable = true;

      # Enable standard desktop services
      services = {
        transmission.enable = true;
        # qdrant/sinevec/etc are heavy, maybe keep them optional or separate?
        # For now, let's keep the bundle focused on "Desktop Infrastructure".
      };
    };
    
    # Enable networking (already defaults to true, but good to be explicit)
    sinnix.networking.enable = true;
  };
}
