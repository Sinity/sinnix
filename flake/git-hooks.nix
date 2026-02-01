# Declarative git hooks via git-hooks.nix
#
# Replaces .pre-commit-config.yaml with Nix-native hook configuration.
# Hooks are automatically installed when entering the dev shell.
#
# Run manually: nix develop -c pre-commit run --all-files
# Check in CI: nix flake check (runs hooks in sandbox)
{ ... }:
{
  perSystem = { config, pkgs, ... }: {
    pre-commit = {
      # Check configuration
      check.enable = true;

      settings = {
        # Exclude patterns
        excludes = [
          "flake\\.lock"
          "secret/.*"
          "\\.age$"
        ];

        hooks = {
          # Nix code quality
          deadnix = {
            enable = true;
            settings.edit = false;  # Report only, don't auto-fix in hook
          };

          # Shell script linting
          shellcheck.enable = true;

          # Note: Formatting is handled by treefmt-nix, not here
          # This prevents double-formatting on commit
        };
      };
    };
  };
}
