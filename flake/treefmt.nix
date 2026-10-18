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
        # Gateway codegen output has exactly one correct form, checked byte
        # for byte by `sinnix-agent-gateway-generate --check`.
        "pkgs/sinnix-agent-gateway/fixtures/*.json"
        "pkgs/sinnix-agent-gateway/sinnix_agent_gateway/generated_*"
        # Rendered by `sinnix-agent-environment-doc`; its renderer owns the form.
        "docs/agent-environment.md"
        # LazyVim rewrites its state file at runtime, without a final newline.
        "dots/nvim/lazyvim.json"
      ];
    };
  };
}
