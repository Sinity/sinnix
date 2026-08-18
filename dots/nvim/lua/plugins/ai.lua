-- The machine's AI lane inside standalone nvim: Claude Code via
-- claudecode.nvim (WebSocket-based IDE integration for the claude CLI) and
-- codex in a project-root terminal. In VS Code the extensions own this.
local in_vscode = vim.g.vscode
return {
  {
    "coder/claudecode.nvim",
    enabled = not in_vscode,
    config = true,
    keys = {
      { "<leader>a", nil, desc = "ai" },
      { "<leader>ac", "<cmd>ClaudeCode<cr>", desc = "Toggle Claude" },
      { "<leader>af", "<cmd>ClaudeCodeFocus<cr>", desc = "Focus Claude" },
      { "<leader>ar", "<cmd>ClaudeCode --resume<cr>", desc = "Resume Claude" },
      { "<leader>aC", "<cmd>ClaudeCode --continue<cr>", desc = "Continue Claude" },
      { "<leader>as", "<cmd>ClaudeCodeSend<cr>", mode = "v", desc = "Send to Claude" },
      {
        "<leader>as",
        "<cmd>ClaudeCodeTreeAdd<cr>",
        desc = "Add file",
        ft = { "NvimTree", "neo-tree", "oil" },
      },
      -- Diff management
      { "<leader>aa", "<cmd>ClaudeCodeDiffAccept<cr>", desc = "Accept diff" },
      { "<leader>ad", "<cmd>ClaudeCodeDiffDeny<cr>", desc = "Deny diff" },
    },
  },
  {
    "folke/snacks.nvim",
    optional = true,
    keys = not in_vscode and {
      {
        "<leader>ax",
        function()
          Snacks.terminal({ "codex" }, { cwd = LazyVim.root() })
        end,
        desc = "Codex (project root)",
      },
    } or {},
  },
}
