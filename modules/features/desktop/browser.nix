{
  pkgs,
  lib,
  config,
  ...
}:
let
  cfg = config.sinnix.features.desktop.browser;
  user = config.sinnix.user.name;
in
{
  options.sinnix.features.desktop.browser = {
    enable = lib.mkEnableOption "Qutebrowser Web Browser";
  };

  config = lib.mkIf cfg.enable {
    home-manager.users.${user} = { pkgs, lib, config, dotsRepoPath, ... }:
      let
        chromeStablePkg = pkgs.google-chrome.override {
          commandLineArgs = "--force-color-profile=srgb";
        };
        mkDotsRepoLink = rel: config.lib.file.mkOutOfStoreSymlink (dotsRepoPath + rel);
        quteDots = rel: mkDotsRepoLink ("/qutebrowser" + rel);
        mkUserScript = name: {
          source = quteDots ("/userscripts/" + name);
        };
      in
      {
        programs.qutebrowser = {
          enable = true;
          package = pkgs.qutebrowser;
        };

        programs.ssh = {
          enable = true;
          enableDefaultConfig = false;
          matchBlocks."*".addKeysToAgent = "yes";
        };

        home = {
          sessionVariables = {
            BROWSER = "google-chrome-stable";
            COMMUNICATION_DOMAIN = "v0.3";
          };

          packages = with pkgs; [
            chromeStablePkg
            qutebrowser
            firefox
            tor-browser
            weechat
            curl
            wget
            nmap
            dig
            traceroute
            whois
            netcat
            socat
            tcpdump
            mtr
            wireshark
            openssh
            mosh
            yt-dlp
            fzf
            jq
            single-file-cli
            wl-clipboard
            neovim-remote
            libnotify
          ];

          file = {
            ".local/share/qutebrowser/userscripts/open-in-mpv" = mkUserScript "open-in-mpv";
            ".local/share/qutebrowser/userscripts/open-in-mpv-audio" = mkUserScript "open-in-mpv-audio";
            ".local/share/qutebrowser/userscripts/yt-related" = mkUserScript "yt-related";
            ".local/share/qutebrowser/userscripts/archive-both" = mkUserScript "archive-both";
            ".local/share/qutebrowser/userscripts/raindrop-save" = mkUserScript "raindrop-save";
            ".local/share/qutebrowser/userscripts/research-capture" = mkUserScript "research-capture";
          };

          activation."qutebrowser-userscripts-perms" = lib.hm.dag.entryAfter [ "writeBoundary" ] ''
            for script in \
              "$HOME/.local/share/qutebrowser/userscripts/open-in-mpv" \
              "$HOME/.local/share/qutebrowser/userscripts/open-in-mpv-audio" \
              "$HOME/.local/share/qutebrowser/userscripts/yt-related" \
              "$HOME/.local/share/qutebrowser/userscripts/archive-both" \
              "$HOME/.local/share/qutebrowser/userscripts/raindrop-save" \
              "$HOME/.local/share/qutebrowser/userscripts/research-capture"
            do
              if [ -e "$script" ]; then
                chmod +x "$script" 2>/dev/null || true
              fi
            done
          '';
        };

        xdg.configFile = {
          "qutebrowser/config.py".source = quteDots "/config.py";
          "qutebrowser/user.css".source = quteDots "/user.css";
          "qutebrowser/greasemonkey/cookie-nag-zapper.user.js".source =
            quteDots "/greasemonkey/cookie-nag-zapper.user.js";
          "qutebrowser/greasemonkey/readable-medium.user.js".source =
            quteDots "/greasemonkey/readable-medium.user.js";
          "qutebrowser/greasemonkey/template.user.js".source = quteDots "/greasemonkey/template.user.js";
        };
      };
  };
}
