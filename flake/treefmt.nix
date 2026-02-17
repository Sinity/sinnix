# Multi-formatter configuration via treefmt-nix
#
# Replaces the simple formatter.nix with a unified multi-formatter setup.
# Run with: nix fmt
# Check with: nix flake check (includes formatting check)
{ ... }:
{
  perSystem =
    { ... }:
    {
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

        # Python formatting (for scripts like mcp-qdrant.py)
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
        ];
      };
    };
}
