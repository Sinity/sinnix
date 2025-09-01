-- VSCode-specific keymaps
-- This file is only loaded when running inside the vscode-neovim extension

-- Check if we are in VSCode
if not vim.g.vscode then
  return
end

local map = vim.keymap.set
local opts = { noremap = true, silent = true }

-- Hybrid Keybinding Examples
-- These keymaps call VSCode commands from Neovim

-- Map <leader>f to open VSCode's fuzzy file finder
map("n", "<leader>f", function()
  vim.fn.VSCodeCall("workbench.action.quickOpen")
end, opts)

-- Map <leader>p to open VSCode's command palette
map("n", "<leader>p", function()
  vim.fn.VSCodeCall("workbench.action.showCommands")
end, opts)

-- Map <leader>t to run the 'Test' task we defined in tasks.json
map("n", "<leader>t", function()
  vim.fn.VSCodeCall("workbench.action.tasks.runTask", "Test")
end, opts)
