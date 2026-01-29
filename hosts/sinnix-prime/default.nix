{ ... }:
{
  imports = [
    ./boot.nix
    ./input.nix
    ./storage.nix
    ./display.nix
  ];

  networking.hostName = "sinnix-prime";

  sinnix.machine.isDesktop = true;

  sinnix.bundles.desktop.enable = true;
  sinnix.bundles.dev.enable = true;

  sinnix.features.dev.editors.enable = true;
  sinnix.features.dev.editors.vscode.enable = true;
  sinnix.features.dev.editors.zed.enable = true;

  sinnix.services = {
    transmission.enable = true;
    # terminal-capture disabled - sinex handles asciinema recording via shell.asciinema.autoRecord
    netdata.enable = true;
    sinex = {
      enable = false;
      provisionDatabase = true;
    };
  };
}
