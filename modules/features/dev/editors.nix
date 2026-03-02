{
  mkFeatureModule,
  lib,
  pkgs,
  ...
}@args:
mkFeatureModule {
  path = [
    "dev"
    "editors"
  ];
  description = "Developer editors (VS Code, Zed)";
  # Using declarative subFeatures instead of manual extraOptions
  subFeatures = {
    vscode = {
      description = "VSCode Editor";
    };
    antigravity = {
      description = "Antigravity Editor (Fork of VSCode)";
    };
    zed = {
      description = "Zed Editor";
    };
  };
  configFn =
    {
      config,
      lib,
      pkgs,
      helpers,
      cfg,
      user,
      ...
    }:
    let
      marketplace = pkgs.nix-vscode-extensions.vscode-marketplace;
    in
    lib.mkMerge [
      (lib.mkIf cfg.vscode.enable {
        home-manager.users.${user} =
          {
            pkgs,
            lib,
            config,
            mkDotsFileFor,
            ...
          }:
          let
            mkDotsFile = mkDotsFileFor config;
          in
          {
            programs.vscode = {
              enable = true;
              mutableExtensionsDir = false;
              profiles.default.extensions =
                (with pkgs.vscode-extensions; [
                  enkia.tokyo-night
                  vscode-icons-team.vscode-icons
                  oderwat.indent-rainbow
                  jnoortheen.nix-ide
                  rust-lang.rust-analyzer
                  tamasfe.even-better-toml
                  asvetliakov.vscode-neovim
                  editorconfig.editorconfig
                ])
                ++ [
                  marketplace.rlivings39.fzf-quick-open
                  marketplace.mkhl.direnv
                  marketplace.vspacecode.whichkey
                  pkgs.vscode-extensions.eamodio.gitlens
                  marketplace.usernamehw.errorlens
                  marketplace.yzhang.markdown-all-in-one
                  marketplace.xiangz19.codex-ratelimit
                ];
            };

            xdg.configFile = {
              "Code/User/settings.json".source = mkDotsFile "/vscode/User/settings.json";
              "Code/User/keybindings.json".source = mkDotsFile "/vscode/User/keybindings.json";
              "Code/User/mcp.json".source = mkDotsFile "/vscode/User/mcp.json";
              "Code/User/mcp" = {
                source = mkDotsFile "/vscode/User/mcp";
                force = true;
              };
            };

            home.activation.cleanupVscodeMcp = lib.hm.dag.entryBefore [ "linkGeneration" ] ''
              rm -rf "$HOME/.config/Code/User/mcp"
            '';

            stylix.targets.vscode.enable = false;
          };
      })

      (lib.mkIf cfg.antigravity.enable {
        home-manager.users.${user} =
          { config, mkDotsFileFor, ... }:
          let
            mkDotsFile = mkDotsFileFor config;
          in
          {
            home.file = {
              ".antigravity/extensions".source = config.lib.file.mkOutOfStoreSymlink "${config.home.homeDirectory}/.vscode/extensions";
            };
            xdg.configFile = {
              "Antigravity/User/settings.json" = {
                source = mkDotsFile "/vscode/User/settings.json";
                force = true;
              };
              "Antigravity/User/keybindings.json" = {
                source = mkDotsFile "/vscode/User/keybindings.json";
                force = true;
              };
            };
            stylix.targets.vscode.enable = false; # Antigravity uses Code settings
          };
      })

      (lib.mkIf cfg.zed.enable {
        home-manager.users.${user} =
          { config, mkDotsFileFor, ... }:
          let
            mkDotsFile = mkDotsFileFor config;
          in
          {
            xdg.configFile = {
              "zed/settings.json".source = mkDotsFile "/zed/settings.json";
              "zed/keymap.json".source = mkDotsFile "/zed/keymap.json";
            };
            # Note: `zed = "zeditor"` alias is defined in shell.nix
          };
      })
    ];
} args
