{
  pkgs,
  inputs,
  lib,
  ...
}:
let
  repoRoot = inputs.self;
  qutePath = "${repoRoot}/qutebrowser";
  mkUserScript = name: {
    source = "${qutePath}/userscripts/${name}";
  };
in
{
  programs.qutebrowser = {
    enable = true;
    package = pkgs.qutebrowser;
  };

  home.packages = with pkgs; [
    qutebrowser
    yt-dlp
    fzf
    jq
    curl
    single-file-cli
    wl-clipboard
    neovim-remote
    libnotify
  ];

  xdg.configFile = {
    "qutebrowser/config.py".source = "${qutePath}/config.py";
    "qutebrowser/user.css".source = "${qutePath}/user.css";
    "qutebrowser/greasemonkey/cookie-nag-zapper.user.js".source =
      "${qutePath}/greasemonkey/cookie-nag-zapper.user.js";
    "qutebrowser/greasemonkey/readable-medium.user.js".source =
      "${qutePath}/greasemonkey/readable-medium.user.js";
    "qutebrowser/greasemonkey/template.user.js".source =
      "${qutePath}/greasemonkey/template.user.js";
  };

  home.file = {
    ".local/share/qutebrowser/userscripts/open-in-mpv" = mkUserScript "open-in-mpv";
    ".local/share/qutebrowser/userscripts/open-in-mpv-audio" = mkUserScript "open-in-mpv-audio";
    ".local/share/qutebrowser/userscripts/yt-related" = mkUserScript "yt-related";
    ".local/share/qutebrowser/userscripts/archive-both" = mkUserScript "archive-both";
    ".local/share/qutebrowser/userscripts/raindrop-save" = mkUserScript "raindrop-save";
    ".local/share/qutebrowser/userscripts/research-capture" = mkUserScript "research-capture";
  };

  home.activation."qutebrowser-userscripts-perms" = lib.hm.dag.entryAfter [ "writeBoundary" ] ''
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
}
