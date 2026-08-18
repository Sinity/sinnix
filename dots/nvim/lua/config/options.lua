-- Options are automatically loaded before lazy.nvim startup
-- Default options that are always set: https://github.com/LazyVim/LazyVim/blob/main/lua/lazyvim/config/options.lua
-- Add any additional options here

vim.opt.title = true
vim.opt.titlestring =
  "%{&readonly?'🔒':''}%{&modified?'✱':''}%f %{&filetype!=#''?'['.&filetype.']':''} ⟪ %{fnamemodify(getcwd(),':~')} ⟫"

-- Project-root detection: same marker set as scripts/lsp-root, so <leader>ff,
-- grep, and terminals agree with how the rest of sinnix resolves a project.
vim.g.root_spec = {
  "lsp",
  { "flake.nix", "Cargo.toml", "pyproject.toml", "go.mod", "package.json", ".git" },
  "cwd",
}

-- Keep lsp.log from growing (error-level only)
vim.lsp.log.set_level(vim.log.levels.ERROR)
