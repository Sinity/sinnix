{
  pkgs,
  inputs,
  lib,
  ...
}:
let
  script = rel: "${inputs.self}/scripts/${rel}";
  configPath = "${inputs.self}/zellij/config.kdl";
 in
{
  home.packages = [ pkgs.zellij ];

  xdg.configFile."zellij/config.kdl".source = configPath;

  home.file = {
    ".local/bin/zellij-session" = {
      source = script "zellij-session";
      executable = true;
    };
    ".local/bin/zed-terminal" = {
      source = script "zed-terminal";
      executable = true;
    };
  };

  home.sessionVariables.ZELLIJ_AUTO_ATTACH = "disable";

  home.activation."zellij-binary-perms" = lib.hm.dag.entryAfter [ "writeBoundary" ] ''
    chmod +x "$HOME/.local/bin/zellij-session" "$HOME/.local/bin/zed-terminal"
  '';
}
