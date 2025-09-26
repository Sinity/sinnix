return {
  -- Prevent Neovim LSP from running when embedded in VS Code
  {
    "neovim/nvim-lspconfig",
    enabled = not vim.g.vscode,
  },
}

