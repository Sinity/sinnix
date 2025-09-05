-- Keymaps are automatically loaded on the VeryLazy event
-- Default keymaps that are always set: https://github.com/LazyVim/LazyVim/blob/main/lua/lazyvim/config/keymaps.lua
-- Add any additional keymaps here

-- In VSCode mode, defer to VSCode keybindings for notes/AI; skip Obsidian maps
if vim.g.vscode then
  return
end

-- Keymaps for Obsidian plugin
local map = vim.keymap.set
local opts = { noremap = true, silent = true }

-- Quick switch, search - somewhat redundant with base fzf-like neovim plugin
map("n", "<leader>oo", ":ObsidianQuickSwitch<CR>", opts)
map("n", "<leader>o/", ":ObsidianSearch<CR>", opts)

-- Backlinks
map("n", "<leader>ob", ":ObsidianBacklinks<CR>", opts)
-- Tags
map("n", "<leader>otg", ":ObsidianTags<CR>", opts)
-- Table of contents
map("n", "<leader>otc", ":ObsidianTOC<CR>", opts)

-- Extract note
map("v", "<leader>oe", ":ObsidianExtractNote<CR>", opts)
-- Rename note
map("n", "<leader>or", ":ObsidianRename<CR>", opts)

-- Create a new note [with title] [from template]
map("n", "<leader>on", ":ObsidianNew<CR>", opts)
map("n", "<leader>ot", ":ObsidianNew ", opts)
map("n", "<leader>oi", ":ObsidianTemplate<CR>", opts)
map("n", "<leader>onf", ":ObsidianNewFromTemplate<CR>", opts)

-- Follow link
map("n", "<leader>ol", ":ObsidianFollowLink<CR>", opts)
map("n", "<leader>ov", ":ObsidianFollowLink vsplit<CR>", opts)
map("n", "<leader>oh", ":ObsidianFollowLink hsplit<CR>", opts)
-- links
map("v", "<leader>ol", ":ObsidianLink<CR>", opts)
map("v", "<leader>ok", ":ObsidianLinkNew<CR>", opts)
map("n", "<leader>ox", ":ObsidianLinks<CR>", opts)

-- Paste image
map("n", "<leader>op", ":ObsidianPasteImg<CR>", opts)
