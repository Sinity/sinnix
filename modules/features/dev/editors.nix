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
  description = "Developer editors (VS Code, Antigravity)";
  subFeatures = {
    vscode = {
      description = "VSCode Editor";
    };
    antigravity = {
      description = "Antigravity Editor (Fork of VSCode)";
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
      waylandEditorFlags =
        "--enable-features=UseOzonePlatform --ozone-platform=wayland "
        + "--disable-features=WaylandWpColorManagerV1,Vulkan,DefaultANGLEVulkan";
      wrapWaylandEditor =
        name: pkg: bin:
        pkgs.symlinkJoin {
          inherit name;
          inherit (pkg)
            meta
            pname
            version
            ;
          paths = [ pkg ];
          passthru = pkg.passthru or { };
          buildInputs = [ pkgs.makeWrapper ];
          postBuild = ''
            wrapProgram $out/bin/${bin} \
              --add-flags "${waylandEditorFlags}"
          '';
        };
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
            vscode-wrapped = wrapWaylandEditor "vscode-wrapped" pkgs.vscode "code";
          in
          {
            programs.vscode = {
              enable = true;
              package = vscode-wrapped;
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

          };
      })

      (lib.mkIf cfg.antigravity.enable {
        sinnix.persistence.home.directories = [
          {
            directory = ".config/Antigravity";
            mode = "0700";
          }
        ];

        home-manager.users.${user} =
          {
            config,
            mkDotsFileFor,
            pkgs,
            ...
          }:
          let
            mkDotsFile = mkDotsFileFor config;
            antigravity-wrapped = wrapWaylandEditor "antigravity-wrapped" pkgs.antigravity "antigravity";
          in
          {
            home.packages = [ antigravity-wrapped ];
            home.file = {
              ".antigravity/extensions".source =
                config.lib.file.mkOutOfStoreSymlink "${config.home.homeDirectory}/.vscode/extensions";
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
          };
      })

    ];
} args
