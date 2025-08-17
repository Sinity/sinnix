# Desktop Applications Configuration
# User applications, tools, and utilities

{ pkgs, ... }:
{
  config = {
    home-manager.users.sinity = {
      home = {
        packages = with pkgs; [
          # XDG mimes dependencies
          junction

          # Desktop applications
          libreoffice
          nautilus
          obsidian
          taskwarrior3
          timewarrior
          bleachbit # cache cleaner
          transmission_3-gtk # BitTorrent client

          # Audio control alternatives
          pulsemixer # TUI alternative to pavucontrol
          pwvucontrol # Modern pipewire GUI

          # Bluetooth alternatives
          bluetuith # Better TUI bluetooth manager
          blueman # GUI bluetooth manager

          # Music
          ncspot # Terminal Spotify client

          # Development and system tools
          evtest # Input device event monitor
          meld # Diff tool
          piper # Mouse configuration
          android-tools
          android-file-transfer
          hledger # Accounting
          llm # CLI for LLMs
          single-file-cli # Save web pages
          programmer-calculator
          bc # Calculator
          calc # Another calculator

          # Audio and media tools
          soundwireserver # Audio streaming (used by hyprland keybind)
          imgur-screenshot
          usbview
          strace # System call tracer
          ltrace # Library call tracer
          nvitop # NVIDIA GPU monitoring
          cage # Wayland kiosk
          wayland-protocols # Wayland development
          vkmark # Vulkan benchmark
          dtach # Screen alternative
          lnch # Application launcher
          at # Job scheduler
          yazi
          glow

          aria2
        ];
      };

      # === XDG MIMES CONFIGURATION ===
      xdg = {
        configFile."mimeapps.list".force = true;
        mimeApps = {
          enable = true;
          associations.added = {
            "text/plain" = [ "org.gnome.TextEditor.desktop" ];
            "image/bmp" = [ "com.interversehq.qView.desktop" ];
            "image/gif" = [ "com.interversehq.qView.desktop" ];
            "image/jpeg" = [ "com.interversehq.qView.desktop" ];
            "image/jpg" = [ "com.interversehq.qView.desktop" ];
            "image/png" = [ "com.interversehq.qView.desktop" ];
            "image/svg+xml" = [ "com.interversehq.qView.desktop" ];
            "image/tiff" = [ "com.interversehq.qView.desktop" ];
            "image/vnd.microsoft.icon" = [ "com.interversehq.qView.desktop" ];
            "image/webp" = [ "com.interversehq.qView.desktop" ];
            "audio/aac" = [ "mpv.desktop" ];
            "audio/mpeg" = [ "mpv.desktop" ];
            "audio/ogg" = [ "mpv.desktop" ];
            "audio/opus" = [ "mpv.desktop" ];
            "audio/wav" = [ "mpv.desktop" ];
            "audio/webm" = [ "mpv.desktop" ];
            "video/mp4" = [ "mpv.desktop" ];
            "video/mkv" = [ "mpv.desktop" ];
            "video/webm" = [ "mpv.desktop" ];
            "video/x-matroska" = [ "mpv.desktop" ];
            "application/pdf" = [ "google-chrome-beta.desktop" ];
          };
          defaultApplications = {
            "text/plain" = [ "org.gnome.TextEditor.desktop" ];
            "image/bmp" = [ "com.interversehq.qView.desktop" ];
            "image/gif" = [ "com.interversehq.qView.desktop" ];
            "image/jpeg" = [ "com.interversehq.qView.desktop" ];
            "image/jpg" = [ "com.interversehq.qView.desktop" ];
            "image/png" = [ "com.interversehq.qView.desktop" ];
            "image/svg+xml" = [ "com.interversehq.qView.desktop" ];
            "image/tiff" = [ "com.interversehq.qView.desktop" ];
            "image/vnd.microsoft.icon" = [ "com.interversehq.qView.desktop" ];
            "image/webp" = [ "com.interversehq.qView.desktop" ];
            "audio/aac" = [ "mpv.desktop" ];
            "audio/mpeg" = [ "mpv.desktop" ];
            "audio/ogg" = [ "mpv.desktop" ];
            "audio/opus" = [ "mpv.desktop" ];
            "audio/wav" = [ "mpv.desktop" ];
            "audio/webm" = [ "mpv.desktop" ];
            "video/mp4" = [ "mpv.desktop" ];
            "video/mkv" = [ "mpv.desktop" ];
            "video/webm" = [ "mpv.desktop" ];
            "video/x-matroska" = [ "mpv.desktop" ];
            "application/pdf" = [ "google-chrome-beta.desktop" ];
            "text/html" = [ "google-chrome-beta.desktop" ];
            "x-scheme-handler/http" = [ "google-chrome-beta.desktop" ];
            "x-scheme-handler/https" = [ "google-chrome-beta.desktop" ];
            "x-scheme-handler/about" = [ "google-chrome-beta.desktop" ];
            "x-scheme-handler/unknown" = [ "google-chrome-beta.desktop" ];
          };
        };
      };
    };
  };
}
