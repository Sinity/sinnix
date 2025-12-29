{ ... }:
{
  imports = [
    ./boot.nix
    ./input.nix
    ./storage.nix
    ./display.nix
  ];

  networking.hostName = "sinnix-prime";
  
  sinnix.bundles.desktop.enable = true;
  sinnix.bundles.dev.enable = true;
  
  sinnix.features.dev.vscode.enable = true;
  sinnix.features.dev.zed.enable = true;
  sinnix.features.cli.asciinema.enable = true;

  sinnix.services = {
    transmission.enable = true;
    qdrant.enable = true;
    sinevec.enable = true;
    asciinema.enable = true;
    polylogue-watch.enable = true;
    sinex = {
      enable = false;
      provisionDatabase = true;
    };
  };
}
