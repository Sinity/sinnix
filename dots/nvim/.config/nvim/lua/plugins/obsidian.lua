local HOME = os.getenv("HOME")
return {
  -- Obsidian Bridge for Sync of Obsidian <=> nvim active buffer
  {
    "oflisback/obsidian-bridge.nvim",
    -- lazy = true,
    -- event = { "BufReadPre ~/home/obsidian/*.md", "BufNewFile ~/home/obsidian/*.md" },
    dependencies = { "nvim-lua/plenary.nvim" },
    opts = {
      obsidian_server_address = "https://127.0.0.1:27124",
      cert_path = HOME .. "/.ssl/obsidian.crt",
      scroll_sync = false,
      warnings = true,
    },
  },

  -- Markdown Oxide LSP
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

  -- Linting for Markdown
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
    -- version = "*", -- recommended, use latest release instead of latest commit
    lazy = true,
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
          path = "~/home/obsidian",
        },
      },
      search_max_lines = 100000,
      templates = {
        folder = "template",
        date_format = "%Y-%m-%d-%a",
        time_format = "%H:%M",
      },
      attachments = {
        img_folder = "asset/img",
      },
      ui = {
        enable = false,
      },
    },
  },
}

-- local HOME = os.getenv("HOME")
-- return {
--   {
--     "oflisback/obsidian-bridge.nvim",
--     opts = {
--       scroll_sync = false,
--       warnings = true,
--       cert_path = "~/.ssl/obsidian.crt",
--     },
--     lazy = true,
--     event = {
--       "BufReadPre *.md",
--       "BufNewFile *.md",
--     },
--     dependencies = {
--       "nvim-lua/plenary.nvim",
--     },
--   },
--   {
--     "epwalsh/obsidian.nvim",
--     -- version = "*", -- recommended, use latest release instead of latest commit
--     lazy = true,
--     ft = "markdown",
--     event = {
--       "BufReadPre *.md",
--       "BufNewFile *.md",
--     },
--     dependencies = {
--       "nvim-lua/plenary.nvim",
--     },
--     opts = {
--       completion = {
--         nvim_cmp = false,
--       },
--       config = function(_, opts)
--         require("obsidian").setup(opts)
--
--         -- HACK: fix error, disable completion.nvim_cmp option, manually register sources
--         local cmp = require("cmp")
--         cmp.register_source("obsidian", require("cmp_obsidian").new())
--         cmp.register_source("obsidian_new", require("cmp_obsidian_new").new())
--         cmp.register_source("obsidian_tags", require("cmp_obsidian_tags").new())
--       end,
--       workspaces = {
--         {
--           name = "obsidian",
--           path = "~/home/obsidian",
--         },
--       },
--       search_max_lines = 100000,
--       templates = {
--         folder = "template",
--         date_format = "%Y-%m-%d-%a",
--         time_format = "%H:%M",
--       },
--       attachments = {
--         img_folder = "asset/img",
--       },
--       ui = {
--         enable = false,
--       },
--     },
--   },
--   {
--     "saghen/blink.cmp",
--     dependencies = { "saghen/blink.compat" },
--     opts = {
--       sources = {
--         default = { "obsidian", "obsidian_new", "obsidian_tags" },
--         providers = {
--           obsidian = {
--             name = "obsidian",
--             module = "blink.compat.source",
--           },
--           obsidian_new = {
--             name = "obsidian_new",
--             module = "blink.compat.source",
--           },
--           obsidian_tags = {
--             name = "obsidian_tags",
--             module = "blink.compat.source",
--           },
--         },
--       },
--     },
--   },
--   {
--     "mfussenegger/nvim-lint",
--     optional = true,
--     opts = {
--       linters = {
--         ["markdownlint-cli2"] = {
--           -- TODO: configure it w/o relying on magic dotfiles I'll forget about eventually
--           args = { "--config", HOME .. "/.config/.markdownlint-cli2.yaml", "--" },
--         },
--       },
--     },
--   },
-- }
