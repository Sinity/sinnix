{ pkgs, ... }:
{
  home.packages = with pkgs; [
    swaybg
    hyprpicker
    wl-gammactl
    wlsunset
  ];
}
