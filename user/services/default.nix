# User-level services
{ ... }:
{
  imports = [
    ./graphical.nix
    ./asciinema.nix
    ./reboot-notifier.nix
  ];
}
