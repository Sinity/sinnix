local HOME = os.getenv("HOME")
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

  {
    "mfussenegger/nvim-lint",
    optional = true,
    opts = {
      linters = {
        ["markdownlint-cli2"] = {
          -- TODO: configure it w/o relying on magic dotfiles I'll forget about eventually
          args = { "--config", HOME .. "/.config/.markdownlint-cli2.yaml", "--" },
        },
      },
    },
  },
  {
    "epwalsh/obsidian.nvim",
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
