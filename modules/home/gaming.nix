{
  pkgs,
  lib,
  ...
}: let
  factorio-auth = pkgs.factorio.override {
    username = "Sinityy";
    token = "TOKEN_REMOVED";
  };
in {
  home.packages = with pkgs; [
    mangohud
    steam-tui
    steam-run

    protonup
    bottles

    factorio-auth

    # prismlauncher # minecraft

    ## Cli games
    _2048-in-terminal
    vitetris
    nethack

    ## Celeste
    celeste-classic
    celeste-classic-pm

    ## Doom
    # gzdoom
    crispy-doom

    ## Emulation
    sameboy
    snes9x
    # cemu
    # dolphin-emu
  ];

  # Unfree packages are now allowed at the system level
}
