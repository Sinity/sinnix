{
  mkFeatureModule,
  pkgs,
  lib,
  ...
}@args:
mkFeatureModule {
  path = [
    "dev"
    "workbench"
  ];
  description = "General development CLI tooling";
  configFn =
    {
      user,
      pkgs,
      ...
    }:
    {
      home-manager.users.${user}.home.packages = with pkgs; [
        stow
        csvkit
        httpie
        websocat
        tokei
        ast-grep
        mprocs
        dtach
        weechat
        graphviz
        mermaid-cli
        android-tools
        evtest
        gcc
        gdb
        git-filter-repo
        gnumake
        google-cloud-sdk
        lm_sensors
        meld
        nvitop
        nix-fast-build
        nix-prefetch-git
        nix-tree
        wireshark
        powertop
        nodePackages_latest.bash-language-server
        nodePackages_latest.yaml-language-server
        sysstat
        strace
        gallery-dl
        vulkan-validation-layers
        wayland-utils
        wayland-protocols
      ];
    };
} args
