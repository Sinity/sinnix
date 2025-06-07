{
  pkgs,
  inputs,
  ...
}:
{
  nixpkgs.overlays = [
    # Apply sinex overlay
    inputs.sinex.overlays.default

    (final: prev: {
      # Override spacy to use a working version
      python3Packages = prev.python3Packages // {
        spacy = prev.python3Packages.spacy.overrideAttrs (old: rec {
          version = "3.8.4"; # last revision that still builds
          src = prev.fetchPypi {
            pname = "spacy";
            inherit version;
            sha256 = "sha256-G92R3l0MP2tqdnSX6uQyH3fF9qqoj4Tns5w8QAM3YCM=";
          };
          meta = old.meta // {
            broken = false;
          };
        });
      };

      # Disable the package causing the issue until a fix is available
      aider-chat-full = prev.aider-chat-full.override {
        pythonPackages = final.python3Packages;
      };

      claude-desktop-wayland = final.symlinkJoin {
        name = "claude-desktop-wayland";
        paths = [
          inputs.claude-desktop.packages.${pkgs.system}.claude-desktop-with-fhs
        ];
        buildInputs = [ final.makeWrapper ];
        postBuild = ''
          wrapProgram $out/bin/claude-desktop --add-flags "--enable-features=WaylandWindowDecorations --no-sandbox"
        '';
      };

      hyprNStack = final.stdenv.mkDerivation {
        pname = "hyprNStack";
        version = "unstable-2024-12-01";

        src = final.fetchFromGitHub {
          owner = "zakk4223";
          repo = "hyprNStack";
          rev = "main";
          sha256 = "sha256-AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA=";
        };

        nativeBuildInputs = with final; [
          pkg-config
          meson
          ninja
        ];

        buildInputs = with final; [
          hyprland.dev
          wayland
          wayland-protocols
          libxkbcommon
          cairo
          pango
          pixman
        ];

        configurePhase = ''
          meson setup build --buildtype=release
        '';

        buildPhase = ''
          ninja -C build
        '';

        installPhase = ''
          mkdir -p $out/lib
          cp build/hyprNStack.so $out/lib/
        '';

        meta = with final.lib; {
          description = "Hyprland plugin for ncolumn/nstack layouts";
          homepage = "https://github.com/zakk4223/hyprNStack";
          license = licenses.bsd3;
          platforms = platforms.linux;
        };
      };
    })
  ];
}
