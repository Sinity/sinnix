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
      # Keep the marketplace subset tiny and explicit so the editor feature does
      # not evaluate the full nix-vscode-extensions marketplace index on every
      # host/test eval. Versions and hashes are pinned from the flake input.
      mkPinnedVscodeMarketplaceExtension =
        {
          publisher,
          name,
          version,
          hash,
          platform ? "universal",
          ...
        }:
        let
          targetPlatform = lib.optionalString (platform != "universal") "targetPlatform=${platform}";
          url =
            "https://${publisher}.gallery.vsassets.io/_apis/public/gallery/publisher/${publisher}"
            + "/extension/${name}/${version}/assetbyname/Microsoft.VisualStudio.Services.VSIXPackage"
            + lib.optionalString (targetPlatform != "") "?${targetPlatform}";
          mktplcRef = {
            inherit
              publisher
              name
              version
              hash
              ;
          };
        in
        pkgs.vscode-utils.buildVscodeMarketplaceExtension {
          inherit mktplcRef;
          vsix = pkgs.fetchurl {
            inherit url hash;
            name = "${publisher}-${name}-${version}.vsix";
          };
        };
      vscodeMarketplacePinned = {
        fzfQuickOpen = mkPinnedVscodeMarketplaceExtension {
          publisher = "rlivings39";
          name = "fzf-quick-open";
          version = "0.5.1";
          hash = "sha256-xGcBl3mmyy+Zsn9OncDDbJViMxEgvsRjkzy89NPJpS8=";
        };
        direnv = mkPinnedVscodeMarketplaceExtension {
          publisher = "mkhl";
          name = "direnv";
          version = "0.17.0";
          hash = "sha256-9sFcfTMeLBGw2ET1snqQ6Uk//D/vcD9AVsZfnUNrWNg=";
        };
        whichkey = mkPinnedVscodeMarketplaceExtension {
          publisher = "VSpaceCode";
          name = "whichkey";
          version = "0.11.4";
          hash = "sha256-mgvI/8Y3naw3Zmud73UYcAEKz6B0Q4tf+0uL3UWcAD0=";
        };
        errorlens = mkPinnedVscodeMarketplaceExtension {
          publisher = "usernamehw";
          name = "errorlens";
          version = "3.28.0";
          hash = "sha256-7eu7y9IR1uxSFZ0IplDieFt3iWbcmdwf1lAcXq+S4C8=";
        };
        markdownAllInOne = mkPinnedVscodeMarketplaceExtension {
          publisher = "yzhang";
          name = "markdown-all-in-one";
          version = "3.4.4";
          hash = "sha256-2lZfWP+yk0Dp8INLjlJY5ROGu0sLaWhb4fT+O9xGg0s=";
        };
        codexRatelimit = mkPinnedVscodeMarketplaceExtension {
          publisher = "xiangz19";
          name = "codex-ratelimit";
          version = "0.12.0";
          hash = "sha256-9uqR4BGXzMh7V1zfKJ8+Zn7tagfVbDXsBh5iS1mzQdk=";
        };
      };
      waylandEditorFlags =
        "--enable-features=UseOzonePlatform --ozone-platform=wayland "
        + "--disable-features=WaylandWpColorManagerV1";
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
            vscodeExtensions = [
              pkgs.vscode-extensions.enkia.tokyo-night
              pkgs.vscode-extensions.vscode-icons-team.vscode-icons
              pkgs.vscode-extensions.oderwat.indent-rainbow
              pkgs.vscode-extensions.jnoortheen.nix-ide
              pkgs.vscode-extensions.rust-lang.rust-analyzer
              pkgs.vscode-extensions.tamasfe.even-better-toml
              pkgs.vscode-extensions.asvetliakov.vscode-neovim
              pkgs.vscode-extensions.editorconfig.editorconfig
              vscodeMarketplacePinned.fzfQuickOpen
              vscodeMarketplacePinned.direnv
              vscodeMarketplacePinned.whichkey
              pkgs.vscode-extensions.eamodio.gitlens
              vscodeMarketplacePinned.errorlens
              vscodeMarketplacePinned.markdownAllInOne
              vscodeMarketplacePinned.codexRatelimit
            ];
          in
          {
            programs.vscode = {
              enable = true;
              package = vscode-wrapped;
              mutableExtensionsDir = false;
              profiles.default = {
                extensions = vscodeExtensions;
                userSettings = mkDotsFile "/vscode/User/settings.json";
                keybindings = mkDotsFile "/vscode/User/keybindings.json";
                userMcp = mkDotsFile "/vscode/User/mcp.json";
              };
            };

            xdg.configFile = {
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
