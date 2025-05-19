{
  pkgs,
  inputs,
  ...
}:
{
  # Import the claude-code-logger module from the flake
  imports = [ inputs.claude-code-logger.homeManagerModules.default ];

  # Configure the claude-code-logger
  programs.claude-code-logger = {
    enable = true;
    logDir = "/realm/observability/claude-code-api-log";
    enableSessionFolders = true;
    enableConversationGrouping = true;
    maxInteractionsPerFile = 100;
    maxLogSizeMB = 10;
    createAlias = true;
  };

  # Development tools and utilities
  home.packages = with pkgs; [
    # Language Servers, Formatters, Linters
    markdown-oxide # Used by obsidian.nvim
    nixfmt-rfc-style # Preferred Nix formatter
    nixd
    nil
    nix-diff

    # Rust development
    rustup
    cargo-fuzz
    cargo-bump
    cargo-audit

    # JavaScript/Node.js
    nodejs
    nodejs_latest

    # Python
    python3
    python3Packages.pip
    python312Packages.ipython

    # Database tools
    sqlite
    sqlitebrowser
    sqlite-vec
    sqlite-utils
    sqlitestudio

    # AI development tools
    aider-chat # aider-chat-full # Temporarily disabled due to spacy dependency issues
    claude-code
    inputs.claude-squad.packages.${pkgs.system}.default # Manage multiple AI coding assistants in isolated workspaces
    claude-desktop-wayland
    codex
    openai-whisper-cpp

    # Development utilities
    jq
    yq
    csvtool
    csvkit
    csvq

    # Git tools
    git
    gh # GitHub CLI
    delta
    lazygit # TUI for git
    onefetch # Git repo stats
  ];

  # Git configuration is already handled in git.nix
}
