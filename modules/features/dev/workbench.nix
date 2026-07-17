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
        # CI workflow authoring, validation, and local reproduction.
        circleci-cli
        act
        actionlint
        yamllint
        hadolint
        # Pre-push security and dependency/image scanning.
        gitleaks
        trivy
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
        powertop
        bash-language-server
        yaml-language-server
        pyright
        sysstat
        strace
        py-spy
        gallery-dl
        vulkan-validation-layers
        wayland-utils
        wayland-protocols
      ];
    };
} args
