{ config, pkgs, lib, ... }:
{
  # Self-inflicted telemetry
  services.activitywatch = {
    enable = true;
    package = pkgs.aw-server-rust;

    watchers = {
      awatcher = {
        package = pkgs.awatcher;
	settings = {
          idle-timeout-seconds = 60;
          poll-time-idle-seconds = 1;
          poll-time-window-seconds = 1;
	};
      };
      # aw-watcher-afk = {
      #   package = pkgs.aw-watcher-afk; # pkgs.activitywatch
      #	settings.poll_time = 1;
      #	settings.timeout = 120;
      # };
      # aw-watcher-window = {
      #   package = pkgs.activitywatch;
      #	settings.exclude_title = false;
      # settings.poll_time = 1;
      # };

      # my-custom-watcher = {
      #   package = pkgs.my-custom-watcher;
      #   executable = "mcw";
      #   settings = {
      #     hello = "there";
      #     enable_greetings = true;
      #     poll_time = 5;
      #   };
      #   settingsFilename = "config.toml";
      # };
    };
    
    # settings = {
    #   timeout = 5;
      # host = "localhost";
      # port = 3012;

      # custom_static = {
      #   my-custom-watcher = "${pkgs.my-custom-watcher}/share/my-custom-watcher/static";
      #   aw-keywatcher = "${pkgs.aw-keywatcher}/share/aw-keywatcher/static";
      # };
    # };

    # extraOptions = ''
    #   "--port"
    #   "5999"
    # '';
  };

  # TODO: make it work(?)
  # programs.zsh.plugins = [ {
  #   name = "aw-watcher-shell";
  #   file = "aw-watcher-shell";
  #   src = pkgs.sources.zsh-plugin_aw-watcher-shell.src;
  # } ];

  # from <https://github.com/Guekka/nixos-server/blob/177721e31bf848ad497d623f136550c41e66a995/home/edgar/optional/activitywatch.nix#L13>
  # from <https://github.com/jordanisaacs/dotfiles/blob/20d6ff59e1a468b9ce5d78fcf169b31c977bd1b9/modules/users/applications/activitywatch.nix#L4>
  # awatcher should start and stop depending on WM session target
  # starting activitywatch should only start awatcher if the WM is active
  systemd.user.services.activitywatch-watcher-awatcher = let
    target = "hyprland-session.target";
  in {
    Unit = {
      After = [target];
      Requisite = [target];
      PartOf = [target];
    };
    Install = { WantedBy = [target]; };
  };

  home.packages = with pkgs; [
    # aw-watcher-window-wayland
    # aw-keywatcher
  ];
}
