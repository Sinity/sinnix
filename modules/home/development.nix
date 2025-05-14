{
  pkgs,
  config,
  lib,
  inputs,
  ...
}: {
  # Development tools and utilities
  home.packages = with pkgs; [
    # Language Servers, Formatters, Linters
    markdown-oxide # Used by obsidian.nvim
    alejandra
    nixd
    nil
    nix-diff
    nixfmt-classic
    
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
    # aider-chat-full # Temporarily disabled due to spacy dependency issues
    aider-chat # Use minimal version without problematic dependencies
    inputs.claude-desktop.packages.${pkgs.system}.claude-desktop-with-fhs
    claude-code
    claude-code-logger
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