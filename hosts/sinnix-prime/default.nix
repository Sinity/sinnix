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

  sinnix.features.cli.task-tracking.enable = true;
  sinnix.features.dev.editors.enable = true;
  sinnix.features.dev.editors.vscode.enable = true;
  sinnix.features.dev.editors.antigravity.enable = true;
  sinnix.features.dev.editors.zed.enable = true;

  sinnix.services = {
    transmission.enable = true;
    terminal-capture.enable = true;
    below.enable = true;
    sinex.enable = false;
    polylogue.enable = false;
    power-watchdog.enable = true;
    sentinel.enable = true;
  };
}
