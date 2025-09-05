-- VSCode-specific keymaps
-- This file is only loaded when running inside the vscode-neovim extension

-- Check if we are in VSCode
if not vim.g.vscode then
  return
end

local vs = require("vscode")
local function map(lhs, cmd, desc)
  vim.keymap.set("n", lhs, function()
    vs.call(cmd)
  end, { silent = true, desc = desc })
end

-- Discovery / palette
map("<leader>?",  "whichkey.show", "WhichKey")
map("<leader>p",  "workbench.action.showCommands", "Command Palette")

-- Files / Search
map("<leader>f",  "workbench.action.quickOpen",   "Quick Open")
map("<leader>e",  "workbench.view.explorer",     "Explorer")
map("<leader>/",  "workbench.action.findInFiles", "Find in Files")
map("<leader>s",  "workbench.view.search",       "Search View")

-- Git
map("<leader>gg", "workbench.view.scm",           "Source Control")

-- Diagnostics
map("<leader>x",  "workbench.actions.view.problems", "Problems")
map("<leader>xn", "editor.action.marker.next",       "Next Problem")
map("<leader>xp", "editor.action.marker.prev",       "Prev Problem")

-- Terminal / Tasks
map("<leader>tt", "workbench.action.terminal.toggleTerminal", "Toggle Terminal")
map("<leader>tn", "workbench.action.terminal.new",            "New Terminal")
map("<leader>tr", "workbench.action.tasks.runTask",           "Run Task…")

-- Debug
map("<leader>dd", "workbench.view.debug",                    "Debug View")
map("<leader>db", "editor.debug.action.toggleBreakpoint",    "Toggle Breakpoint")
map("<leader>dc", "workbench.action.debug.continue",         "Debug Continue")
map("<leader>do", "workbench.action.debug.stepOver",         "Debug Step Over")
map("<leader>di", "workbench.action.debug.stepInto",         "Debug Step Into")

-- Rust / Nix
map("<leader>ra", "editor.action.codeAction",                "Code Action")
map("<leader>rr", "rust-analyzer.run",                       "Rust Analyzer: Run")
map("<leader>rt", "testing.runAll",                          "Run All Tests")
map("<leader>nc", "workbench.action.tasks.runTask",          "Run Task… (Nix)")
map("<leader>ns", "workbench.action.tasks.runTask",          "Run Task… (Nix Switch)")

-- Notes / Markdown / Foam
map("<leader>mp", "markdown.showPreviewToSide",              "Markdown Preview to Side")
map("<leader>mg", "foam-vscode.show-graph",                  "Foam: Show Graph")

-- Layout
map("<leader>sv", "workbench.action.splitEditorRight",       "Split Right")
map("<leader>sh", "workbench.action.splitEditorDown",        "Split Down")
map("<leader>w=", "workbench.action.evenEditorWidths",       "Even Widths")

-- Hover on K to mirror LSP hover
map("K",         "editor.action.showHover",                  "Show Hover")

-- LSP-like navigation (VS Code actions) on <leader>l…
map("<leader>ld", "editor.action.revealDefinition",          "Go to Definition")
map("<leader>lD", "editor.action.revealDeclaration",         "Go to Declaration")
map("<leader>lI", "editor.action.goToImplementation",        "Go to Implementation")
map("<leader>lT", "editor.action.goToTypeDefinition",        "Go to Type Definition")
map("<leader>lR", "editor.action.referenceSearch.trigger",   "Find References")
map("<leader>lp", "editor.action.peekDefinition",            "Peek Definition")
map("<leader>lr", "editor.action.rename",                    "Rename Symbol")
