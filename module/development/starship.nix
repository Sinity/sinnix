# Simple Starship Configuration with clean directory display
{
  config,
  ...
}:

{
  config = {
    home-manager.users.sinity = {
      programs.starship = {
        enable = true;
        enableBashIntegration = true;
        enableZshIntegration = true;
        enableNushellIntegration = true;

        settings = {
          format = "$directory $git_branch$git_status$nix_shell$character";
          right_format = "$cmd_duration$jobs$status$time";

          directory = {
            format = "[$path]($style)";
            style = "cyan bold";

            # Use fish-style abbreviation
            fish_style_pwd_dir_length = 1;

            # Replace $HOME with ~
            home_symbol = "~";

            # Don't truncate to repo - show full fish-style path
            truncate_to_repo = false;
          };

          git_branch = {
            format = "[$branch]($style)";
            style = "yellow";
            only_attached = true;
          };

          git_status = {
            format = "([$all_status$ahead_behind]($style))";
            style = "red";
            conflicted = "=";
            ahead = "⇡";
            behind = "⇣";
            diverged = "⇕";
            untracked = "?";
            stashed = "\\$"; # Escape the $ character
            modified = "*";
            staged = "+";
            renamed = "»";
            deleted = "✘";
          };

          nix_shell = {
            format = "[$symbol]($style)";
            symbol = "❄️";
            style = "blue bold";
            impure_msg = "[❄️](red bold)";
            pure_msg = "[❄️](blue bold)";
          };

          cmd_duration = {
            format = "[$duration]($style)";
            style = "yellow dimmed";
            min_time = 3000;
            show_milliseconds = false;
          };

          character = {
            success_symbol = "[❯](bold green)";
            error_symbol = "[❯](bold red)";
            vimcmd_symbol = "[❮](bold green)";
          };

          time = {
            disabled = false;
            format = "[$time]($style)";
            time_format = "%H:%M";
            style = "dimmed";
          };

          status = {
            disabled = false;
            format = "[$symbol$status]($style)";
            symbol = "✘";
            style = "red";
            map_symbol = true;
            pipestatus = true;
          };

          jobs = {
            format = "[$symbol$number]($style)";
            symbol = "⚡";
            style = "yellow";
            threshold = 1;
          };
        };
      };
    };
  };
}
