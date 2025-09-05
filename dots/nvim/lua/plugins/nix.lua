return {
  -- Add nix to treesitter
  -- {
  --   "nvim-treesitter/nvim-treesitter",
  --   opts = function(_, opts)
  --     if type(opts.ensure_installed) == "table" then
  --       vim.list_extend(opts.ensure_installed, { "nix" })
  --     end
  --   end,
  -- },
  {
    "nvim-treesitter/nvim-treesitter",
    opts = { ensure_installed = { "nix" } },
  },

  -- Configure LSP for Nix
  {
    "neovim/nvim-lspconfig",
    opts = {
      servers = {
        nixd = {
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
              loglevel = "error", -- Reduce logging to only errors
            },
          },
        },
      },
      -- Disable automatic server setup since nixd comes from system
      -- setup = {
      --   nixd = function(_, _)
      --     return false -- Let lspconfig handle setup
      --   end,
      -- },
    },
  },

  -- Add formatter
  {
    "stevearc/conform.nvim",
    opts = {
      formatters_by_ft = {
        nix = { "nixfmt" },
      },
    },
  },

  -- Add some extra keymaps for Nix files
  -- {
  --   "LazyVim/LazyVim",
  --   opts = {
  --     autocmds = {
  --       custom = {
  --         {
  --           "FileType",
  --           {
  --             pattern = "nix",
  --             callback = function()
  --               vim.keymap.set("n", "<leader>ne", function()
  --                 local filename = vim.fn.expand("%:p")
  --                 vim.cmd("!" .. "nix eval -f " .. vim.fn.shellescape(filename))
  --               end, { buffer = true, desc = "Evaluate Nix file" })
  --             end,
  --           },
  --         },
  --       },
  --     },
  --   },
  -- },
}
