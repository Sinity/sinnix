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

  sinnix.paths.projectRoot = "/realm/project/sinnix";

  sinnix.bundles.desktop.enable = true;
  sinnix.bundles.dev.enable = true;

  sinnix.features.dev.editors.vscode.enable = true;
  sinnix.features.dev.editors.zed.enable = true;
  sinnix.features.cli.asciinema.enable = true;

  # Ensure dev shell is explicitly enabled (though bundle covers it)
  sinnix.features.dev.shell.enable = true;

  sinnix.services = {
    transmission.enable = true;
    qdrant.enable = false;
    sinevec.enable = false;
    asciinema.enable = true;
    polylogue.enable = true;
    sinex = {
      enable = false;
      provisionDatabase = true;
    };
  };
}
