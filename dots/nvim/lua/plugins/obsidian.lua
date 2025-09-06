local HOME = os.getenv("HOME")
local in_vscode = vim.g.vscode
return {
  {
    "neovim/nvim-lspconfig",
    opts = {
      servers = {
        markdown_oxide = {},
        marksman = {
          enabled = false, -- Disable Marksman
        },
      },
    },
  },

  -- Disable nvim-lint in VSCode mode
  {
    "mfussenegger/nvim-lint",
    enabled = not in_vscode,
    optional = true,
    opts = {
      linters = {
        ["markdownlint-cli2"] = {
          args = { "--config", HOME .. "/.config/.markdownlint-cli2.yaml", "--" },
        },
      },
    },
  },
  -- Disable Obsidian.nvim in VSCode mode
  {
    "epwalsh/obsidian.nvim",
    enabled = not in_vscode,
    version = "*",
    lazy = false,
    ft = "markdown",
    event = {
      "BufReadPre *.md",
      "BufNewFile *.md",
    },
    dependencies = {
      "nvim-lua/plenary.nvim",
    },
    opts = {
      completion = {
        nvim_cmp = false,
      },
      workspaces = {
        {
          name = "obsidian",
          path = "/realm/knowledgebase/",
        },
      },
      search_max_lines = 1000000,
      templates = {
        folder = "60_templates",
        date_format = "%Y-%m-%d-%a",
        time_format = "%H:%M",
      },
      attachments = {
        img_folder = "80_media",
      },
      ui = {
        enable = false,
      },
    },
  },
}
