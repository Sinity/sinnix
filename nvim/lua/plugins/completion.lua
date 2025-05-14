return {
  {
    "saghen/blink.cmp",
    opts = {
      completion = {
        menu = {
          max_height = 120,
        },
      },
    },
  },
  -- Make blink.cmp toogleable
  {
    "saghen/blink.cmp",
    opts = function(_, opts)
      vim.b.completion = true

      Snacks.toggle({
        name = "Completion",
        get = function()
          return vim.b.completion
        end,
        set = function(state)
          vim.b.completion = state
        end,
      }):map("<leader>uk")

      opts.enabled = function()
        return vim.b.completion ~= false
      end
      return opts
    end,
  },
}
