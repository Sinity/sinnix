{
  programs.kitty = {
    enable = true;
    settings = {
      window_padding_width = 10;
      scrollback_lines = 9999999;
      enable_audio_bell = "no";
      mouse_hide_wait = 60;
      wheel_scroll_multiplier = 5.0;
      touch_scroll_multiplier = 5.0;
      cursor_trail = 3;
      confirm_os_window_close = 0;
      allow_remote_control = "socket-only";
      listen_on = "unix:" + "\${XDG_RUNTIME_DIR}/kitty-" + "\${USER}";
      open_url_with = "xdg-open";
      detect_urls = "yes";
      url_prefixes = "http https file ftp";
      url_style = "single";
      allow_hyperlinks = "yes";
      tab_title_template = "{title}";
      active_tab_font_style = "normal";
      inactive_tab_font_style = "normal";
      tab_bar_style = "powerline";
      tab_powerline_style = "angled";
    };
    extraConfig = ''
      map ctrl+shift+f12 debug_config

      map ctrl+shift+enter launch --type=tab --cwd=current zellij-session project
      # map ctrl+shift+space launch --type=overlay --cwd=current zellij-session scratch

      shell_integration enabled
    '';
  };
}
