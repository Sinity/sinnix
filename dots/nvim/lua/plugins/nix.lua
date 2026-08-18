return {
  {
    "nvim-treesitter/nvim-treesitter",
    opts = { ensure_installed = { "nix" } },
  },

  -- nixd comes from the system profile (modules/features/dev/languages.nix),
  -- not Mason: Mason has no working nixd on NixOS, which previously left nix
  -- files without any LSP at all.
  {
    "neovim/nvim-lspconfig",
    opts = {
      servers = {
        nixd = {
          mason = false,
          settings = {
            nixd = {
              formatting = {
                command = { "nixfmt" },
              },
              options = {
                enable = true,
                target = {
                  args = {},
                  enable = true,
                  installable = true,
                },
              },
            },
          },
        },
      },
    },
  },

  {
    "stevearc/conform.nvim",
    enabled = not vim.g.vscode,
    opts = {
      formatters_by_ft = {
        nix = { "nixfmt" },
      },
    },
  },
}
