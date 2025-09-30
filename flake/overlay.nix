{
  inputs,
  ...
}:
let
  sinexOverlays =
    if builtins.getEnv "SINEX_DISABLE" == "1" then
      [ ]
    else if inputs ? sinex && inputs.sinex ? overlays && inputs.sinex.overlays ? default then
      [ inputs.sinex.overlays.default ]
    else
      [ ];
in
{
  nixpkgs.overlays = sinexOverlays ++ [
    # Community overlay providing large set of VSCode extensions
    inputs.nix-vscode-extensions.overlays.default

    (final: prev: {
      # Override Codex CLI to a newer upstream tag
      codex = prev.codex.overrideAttrs (
        _old:
        let
          version = "0.42.0";
          newSrc = final.fetchFromGitHub {
            owner = "openai";
            repo = "codex";
            rev = "refs/tags/rust-v" + version;
            sha256 = "sha256-YyI4quZ1vcwzDx38EzqycnUQDBOg9SfEemR4zdKYYIw=";
          };
          newCargo = final.rustPlatform.fetchCargoVendor {
            src = newSrc;
            sourceRoot = "source/codex-rs";
            hash = "sha256-No6/WmaCI+w1cVD+PsLJ1jK0zZDYziGlm9DD9E3hA58=";
          };
        in
        {
          inherit version;
          src = newSrc;
          cargoDeps = newCargo;
        }
      );
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

      # claude-desktop-wayland = final.symlinkJoin {
      #   name = "claude-desktop-wayland";
      #   paths = [
      #     inputs.claude-desktop.packages.${pkgs.system}.claude-desktop-with-fhs
      #   ];
      #   buildInputs = [ final.makeWrapper ];
      #   postBuild = ''
      #     wrapProgram $out/bin/claude-desktop --add-flags "--enable-features=WaylandWindowDecorations --no-sandbox"
      #   '';
      # };

      claude-code-usage-monitor = final.python3Packages.buildPythonApplication {
        pname = "claude-code-usage-monitor";
        version = "unstable";
        src = inputs.claude-code-usage-monitor-src;

        pyproject = true;
        build-system = with final.python3Packages; [ setuptools ];

        propagatedBuildInputs = with final.python3Packages; [
          pytz
          requests
          beautifulsoup4
          lxml
          numpy
          pydantic
          pydantic-settings
          pyyaml
          rich
        ];

        # Use standard Python package installation instead of custom script install
        postInstall = ''
          # The package should install the console script via setuptools entry points
        '';

        meta = with final.lib; {
          description = "Real-time terminal monitoring tool for tracking Claude AI token usage";
          homepage = "https://github.com/Maciek-roboblog/Claude-Code-Usage-Monitor";
          license = licenses.mit;
        };
      };
    })
  ];
}
