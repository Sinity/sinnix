{
  imports = [
    ./boot.nix
    ./hardware.nix
    ./storage.nix
    ./audio.nix
    ./display.nix
  ];

  sinnix.services = {
    transmission.enable = true;
    postgresql.enable = true;
    photoprism.enable = true;
    qdrant.enable = true;
  };

  sinnix.media.pipewire.enable = true;
  sinnix.networking.enable = true;
}
