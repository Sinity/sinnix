# module/desktop/themes.nix
{
  pkgs,
  ...
}:
{
  # --- GTK Config ---
  gtk = {
    enable = true;
    theme = {
      name = "Gruvbox-Dark";
      package = pkgs.gruvbox-gtk-theme.override { colorVariants = [ "dark" ]; };
    };
    iconTheme = {
      name = "Papirus-Dark";
      package = pkgs.papirus-icon-theme.override { color = "black"; };
    };
    cursorTheme = {
      name = "Bibata-Modern-Ice";
      size = 24;
      package = pkgs.bibata-cursors;
    };
    # font = { name = "JetBrainsMono NF"; size = 11; }; # Uncomment if needed
  };

  home.file.".icons/default/index.theme".text = ''
    [Icon Theme]
    Inherits=Bibata-Modern-Ice
  '';
}
