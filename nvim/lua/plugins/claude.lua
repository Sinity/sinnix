return {
  {
    "coder/claudecode.nvim",
    config = true,
    keys = {
      { "<leader>ac", "<cmd>ClaudeCode<cr>", desc = "Toggle Claude" },
      { "<leader>af", "<cmd>ClaudeCodeFocus<cr>", desc = "Focus Claude" },
      { "<leader>as", "<cmd>ClaudeCodeSend<cr>", mode = "v", desc = "Send to Claude" },
    },
    opts = {
      auto_start = true,
      log_level = "info",
      terminal = {
        split_side = "right",
        split_width_percentage = 0.3,
        provider = "auto",
        auto_close = true,
      },
    },
  },
}