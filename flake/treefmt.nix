# Multi-formatter configuration via treefmt-nix
#
# Run with: nix fmt
# Check with: nix flake check (includes formatting check)
_: {
  perSystem = _: {
    treefmt = {
      # Identify project root
      projectRootFile = "flake.nix";

      # Nix formatting
      programs.nixfmt.enable = true;

      # Shell script formatting
      programs.shfmt = {
        enable = true;
        indent_size = 2;
      };

      # YAML/JSON formatting
      programs.prettier = {
        enable = true;
        includes = [
          "*.json"
          "*.yaml"
          "*.yml"
          "*.md"
        ];
        settings = {
          tabWidth = 2;
          proseWrap = "preserve";
        };
      };

      # Python formatting for repository scripts
      programs.ruff = {
        enable = true;
        format = true;
      };

      # Exclude generated/external files
      settings.global.excludes = [
        "flake.lock"
        "*.age" # Encrypted secrets
        "result"
        ".direnv/*"
        "secret/*"
        # Prettier can't parse personas.yaml (unicode box-drawing in comments)
        "dots/claude/skills/persona/personas.yaml"
        # The phone app's Gradle dependency lock is written by mitm-cache's
        # update script, wholesale, every time it runs. Formatting it would
        # make every regeneration a several-hundred-line diff against a file
        # nobody reads by hand.
        "pkgs/sinnix-phone-app/deps.json"
      ];
    };
  };
}
