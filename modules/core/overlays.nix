{lib, ...}: {
  nixpkgs.overlays = [
    (final: prev: {
      # Override spacy to use a working version
      python3Packages =
        prev.python3Packages
        // {
          spacy = prev.python3Packages.spacy.overrideAttrs (old: rec {
            version = "3.8.4"; # last revision that still builds
            src = prev.fetchPypi {
              pname = "spacy";
              inherit version;
              sha256 = "sha256-G92R3l0MP2tqdnSX6uQyH3fF9qqoj4Tns5w8QAM3YCM=";
            };
            meta = old.meta // {broken = false;};
          });
        };

      # Disable the package causing the issue until a fix is available
      aider-chat-full = prev.aider-chat-full.override {
        pythonPackages = final.python3Packages;
      };

      claude-code-logger = prev.callPackage ../../pkgs/claude-code-logger.nix {};
    })
  ];
}
