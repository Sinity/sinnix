{
  inputs,
  pkgs,
  system,
}:
let
  resolveFlakeDir = ''
    _flake_dir="''${PRJ_ROOT:-$(git rev-parse --show-toplevel 2>/dev/null || pwd)}"
  '';
in
{
  appCommands = {
    lint = {
      description = "Lint Nix and shell files without modifying sources";
      script = ''
        ${resolveFlakeDir}
        cd "$_flake_dir"
        echo "Running deadnix..."
        ${pkgs.deadnix}/bin/deadnix --fail .
        echo "Running statix..."
        ${pkgs.statix}/bin/statix check

        echo "Running shellcheck on shell helpers..."
        ${pkgs.fd}/bin/fd -t f -e sh -x ${pkgs.shellcheck}/bin/shellcheck {}
        shellcheck_targets="$(${pkgs.ripgrep}/bin/rg -Il '^#!.*\\b(bash|sh|zsh)\\b' scripts || true)"
        if [ -n "$shellcheck_targets" ]; then
          while IFS= read -r target; do
            [ -n "$target" ] && ${pkgs.shellcheck}/bin/shellcheck "$target"
          done <<<"$shellcheck_targets"
        fi

        echo "Linting complete!"
      '';
    };

    test = {
      description = "Test configuration without applying it to the system";
      script = ''
        ${resolveFlakeDir}
        if [ "$(id -u)" -ne 0 ]; then
          echo "Error: This command must be run as root (use 'sudo nix run $_flake_dir#test')"
          exit 1
        fi
        ${pkgs.nixos-rebuild}/bin/nixos-rebuild test --flake "$_flake_dir#sinnix-prime" \
          --log-format internal-json -v 2>&1 | ${pkgs.nix-output-monitor}/bin/nom --json
      '';
    };

    switch = {
      description = "Apply configuration changes to the system";
      script = ''
        ${resolveFlakeDir}
        if [ "$(id -u)" -ne 0 ]; then
          echo "Error: This command must be run as root (use 'sudo nix run $_flake_dir#switch')"
          exit 1
        fi
        ${pkgs.nixos-rebuild}/bin/nixos-rebuild switch --flake "$_flake_dir#sinnix-prime" \
          --log-format internal-json -v 2>&1 | ${pkgs.nix-output-monitor}/bin/nom --json
      '';
    };

    clean = {
      description = "Clean up old system generations and optimize nix store";
      script = ''
        if [ "$(id -u)" -ne 0 ]; then
          echo "Error: This command must be run as root (use 'sudo nix run .#clean')"
          exit 1
        fi
        echo "Removing old system generations..."
        if ! nix profile wipe-history --profile /nix/var/nix/profiles/system --older-than 30d >/dev/null 2>&1; then
          echo "nix profile wipe-history unavailable, falling back to nix-env"
          nix-env --delete-generations old --profile /nix/var/nix/profiles/system
        fi

        echo "Optimizing nix store..."
        nix store optimise

        echo "Collecting garbage..."
        nix store gc

        echo "System cleanup complete."
      '';
    };

    agenix = {
      description = "Manage encrypted secrets with agenix";
      script = ''
        ${inputs.agenix.packages.${system}.default}/bin/agenix "$@"
      '';
    };
  };

  commandDocs = [
    {
      name = "check";
      command = "nix flake check";
      description = "Validate flake outputs and config assertion tests";
    }
    {
      name = "format";
      command = "nix fmt";
      description = "Format configured filetypes via treefmt";
    }
    {
      name = "update";
      command = "nix flake update";
      description = "Update flake inputs";
    }
    {
      name = "lint";
      command = "nix run .#lint";
      description = "Run deadnix/statix/shellcheck";
    }
    {
      name = "test";
      command = "sudo nix run .#test";
      description = "Build and test host config without switching";
    }
    {
      name = "switch";
      command = "sudo nix run .#switch";
      description = "Apply host config";
    }
    {
      name = "clean";
      command = "sudo nix run .#clean";
      description = "Prune generations and garbage collect";
    }
    {
      name = "agenix";
      command = "nix run .#agenix";
      description = "Manage encrypted secrets";
    }
  ];
}
