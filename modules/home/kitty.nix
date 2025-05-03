# modules/home/kitty.nix
{
  pkgs,
  lib,
  ...
}: let
  # Gruvbox Dark theme content
  gruvboxDarkTheme = ''
    # Gruvbox Dark theme for Kitty
    # Based on https://github.com/morhetz/gruvbox

    # Basic colors
    foreground            #ebdbb2
    background            #282828
    selection_foreground  #928374
    selection_background  #ebdbb2

    # Cursor colors
    cursor                #bdae93
    cursor_text_color     #665c54

    # URL underline color when hovering
    url_color             #83a598

    # Window border colors
    active_border_color   #d3869b
    inactive_border_color #665c54

    # Tab bar colors
    active_tab_foreground #fbf1c7
    active_tab_background #7c6f64
    inactive_tab_foreground #fbf1c7
    inactive_tab_background #3c3836

    # Normal colors
    color0                #282828
    color1                #cc241d
    color2                #98971a
    color3                #d79921
    color4                #458588
    color5                #b16286
    color6                #689d6a
    color7                #a89984

    # Bright colors
    color8                #928374
    color9                #fb4934
    color10               #b8bb26
    color11               #fabd2f
    color12               #83a598
    color13               #d3869b
    color14               #8ec07c
    color15               #ebdbb2

    # Extended colors
    color16               #fe8019
    color17               #d65d0e
    color18               #3c3836
    color19               #504945
    color20               #bdae93
    color21               #ebdbb2
  '';
in {
  programs.kitty = {
    enable = true; # Keep enabled
    # shell = "nu"; # Set shell to nu
    # shellIntegration.enable = true; # Enable shell integration
    font = {
      name = "FiraCode Nerd Font"; # Update font name
      size = 16; # Update font size
    };
    settings = {
      # Window settings
      background_opacity = "0.90";
      window_padding_width = 10;
      scrollback_lines = 10000;
      enable_audio_bell = "no";
      mouse_hide_wait = 60;
      wheel_scroll_multiplier = 0.5;
      touch_scroll_multiplier = 0.5;
      cursor_trail = 3;
      confirm_os_window_close = 0;

      # Remote control
      allow_remote_control = "yes";
      listen_on = "unix:/tmp/kitty";

      # URL handling
      open_url_with = "xdg-open";
      detect_urls = "yes";
      url_prefixes = "http https file ftp";
      url_style = "single";
      allow_hyperlinks = "yes";

      # Tab settings (Theme colors are handled by gruvboxDarkTheme below)
      tab_title_template = "{title}";
      active_tab_font_style = "normal";
      inactive_tab_font_style = "normal";
      tab_bar_style = "powerline";
      tab_powerline_style = "angled";
    };
    # Include the theme content and extra config from kitty.conf
    extraConfig =
      gruvboxDarkTheme
      + ''        # Keep theme and debug map
             map ctrl+shift+f12 debug_config
      '';
    # Keyboard shortcuts
    keybindings = {
      "alt+1" = "goto_tab 1";
      "alt+2" = "goto_tab 2";
      "alt+3" = "goto_tab 3";
      "alt+4" = "goto_tab 4";
      "ctrl+shift+left" = "no_op";
      "ctrl+shift+right" = "no_op";
    };
  };
}
