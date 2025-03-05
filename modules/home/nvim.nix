{
  inputs,
  pkgs,
  username,
  ...
}: {
  imports = [
    inputs.nvchad4nix.homeManagerModule
  ];

  programs.nvchad4nix.enable = true;
  # programs.nvf = {
  #   enable = true;
  #   settings = {
  #     vim = {
  #       viAlias = true;
  #       vimAlias = true;
  #       debugMode = {
  #         enable = false;
  #         level = 16;
  #         logFile = "/tmp/nvim.log";
  #       };
  #
  #       spellcheck.enable = false;
  #
  #       lsp = {
  #         formatOnSave = true;
  #         lspkind.enable = false;
  #         lightbulb.enable = true;
  #         lspsaga.enable = false;
  #         trouble.enable = true;
  #         lspSignature.enable = true;
  #         otter-nvim.enable = true;
  #         # lsplines.enable = true;
  #         nvim-docs-view.enable = true;
  #       };
  #
  #       debugger = {
  #         nvim-dap = {
  #           enable = true;
  #           ui.enable = true;
  #         };
  #       };
  #
  #       languages = {
  #         enableLSP = true;
  #         enableFormat = true;
  #         enableTreesitter = true;
  #         enableExtraDiagnostics = true;
  #
  #         nix.enable = true;
  #
  #         markdown.enable = true;
  #         bash.enable = true;
  #         clang.enable = true;
  #         css.enable = true;
  #         html.enable = true;
  #         sql.enable = true;
  #         ts.enable = true;
  #         lua.enable = true;
  #         python.enable = true;
  #         rust = {
  #           enable = true;
  #           crates.enable = true;
  #         };
  #       };
  #
  #       visuals = {
  #         nvim-scrollbar.enable = true;
  #         nvim-web-devicons.enable = true;
  #         nvim-cursorline.enable = true;
  #         cinnamon-nvim.enable = true;
  #         fidget-nvim.enable = true;
  #         highlight-undo.enable = true;
  #         indent-blankline.enable = true;
  #         cellular-automaton.enable = false;
  #       };
  #
  #       statusline = {
  #         lualine = {
  #           enable = true;
  #           theme = "catppuccin";
  #         };
  #       };
  #
  #       theme = {
  #         enable = true;
  #         name = "catppuccin";
  #         style = "mocha";
  #         transparent = false;
  #       };
  #
  #       autopairs.nvim-autopairs.enable = true;
  #
  #       autocomplete.nvim-cmp.enable = true;
  #       snippets.luasnip.enable = true;
  #
  #       filetree = {
  #         neo-tree = {
  #           enable = true;
  #         };
  #       };
  #
  #       tabline = {
  #         nvimBufferline.enable = true;
  #       };
  #
  #       # treesitter.context.enable = true;
  #
  #       binds = {
  #         whichKey.enable = true;
  #         cheatsheet.enable = true;
  #       };
  #
  #       telescope.enable = true;
  #
  #       git = {
  #         enable = true;
  #         gitsigns.enable = true;
  #         gitsigns.codeActions.enable = false; # throws an annoying debug message
  #       };
  #
  #       minimap = {
  #         minimap-vim.enable = false;
  #         codewindow.enable = true; # lighter, faster, and uses lua for configuration
  #       };
  #
  #       dashboard = {
  #         dashboard-nvim.enable = false;
  #         alpha.enable = true;
  #       };
  #
  #       notify = {
  #         nvim-notify.enable = true;
  #       };
  #
  #       projects = {
  #         project-nvim.enable = true;
  #       };
  #
  #       utility = {
  #         preview.glow.enable = true;
  #         ccc.enable = false;
  #         vim-wakatime.enable = false;
  #         icon-picker.enable = true;
  #         surround.enable = true;
  #         diffview-nvim.enable = true;
  #         yanky-nvim.enable = false;
  #         motion = {
  #           hop.enable = true;
  #           leap.enable = true;
  #           # precognition.enable = true;
  #         };
  #
  #         images = {
  #           image-nvim.enable = false;
  #         };
  #       };
  #
  #       notes = {
  #         obsidian = {
  #           enable = true;
  #           setupOpts.workspaces = [
  #             {
  #               name = "exocortex";
  #               path = "/mnt/ssd_storage/home/obsidian";
  #             }
  #           ];
  #         };
  #         neorg.enable = false;
  #         orgmode.enable = false;
  #         mind-nvim.enable = true;
  #         todo-comments.enable = true;
  #       };
  #
  #       terminal = {
  #         toggleterm = {
  #           enable = true;
  #           lazygit.enable = true;
  #         };
  #       };
  #
  #       ui = {
  #         borders.enable = true;
  #         noice.enable = true;
  #         colorizer.enable = true;
  #         modes-nvim.enable = false; # the theme looks terrible with catppuccin
  #         illuminate.enable = true;
  #         breadcrumbs = {
  #           enable = true;
  #           navbuddy.enable = true;
  #         };
  #         smartcolumn = {
  #           enable = true;
  #           setupOpts.custom_colorcolumn = {
  #             nix = "110";
  #             ruby = "120";
  #             java = "130";
  #             go = ["90" "130"];
  #           };
  #         };
  #         fastaction.enable = true;
  #       };
  #
  #       assistant = {
  #         chatgpt.enable = false;
  #         copilot = {
  #           enable = false;
  #           cmp.enable = true;
  #         };
  #       };
  #
  #       session = {
  #         nvim-session-manager.enable = false;
  #       };
  #
  #       gestures = {
  #         gesture-nvim.enable = false;
  #       };
  #
  #       comments = {
  #         comment-nvim.enable = true;
  #       };
  #
  #       presence = {
  #         neocord.enable = false;
  #       };
  #     };
  #   };
  # };
  #
  # programs.nixvim = {
  #   enable = true;
  #   vimAlias = true;
  #   defaultEditor = true;
  #
  #   globals = {
  #     mapleader = " ";
  #     rainbow_active = 1;
  #   };
  #
  #   opts = {
  #     # File handling
  #     autoread = true;
  #     hidden = true;
  #     backup = false;
  #     writebackup = false;
  #     swapfile = false;
  #
  #     # Editor behavior
  #     cpoptions = "ces$";
  #     expandtab = true;
  #     shiftwidth = 2;
  #     softtabstop = 2;
  #     tabstop = 2;
  #     autoindent = true;
  #
  #     # Display and UI
  #     number = true;
  #     relativenumber = true;
  #     cursorline = false;
  #     showmatch = true;
  #     wrap = false;
  #     laststatus = 3;
  #     signcolumn = "yes";
  #     termguicolors = true;
  #     scrolloff = 4;
  #     scrolljump = 5;
  #
  #     # Search and replace
  #     ignorecase = true;
  #     smartcase = true;
  #     hlsearch = true;
  #     incsearch = true;
  #     wrapscan = true;
  #     gdefault = true;
  #
  #     # Window and buffer handling
  #     switchbuf = "useopen";
  #     splitbelow = true;
  #     splitright = true;
  #     whichwrap = "<,>,[,]";
  #
  #     # Completion and menus
  #     completeopt = "menu,menuone,noselect";
  #     pumheight = 10;
  #     wildmenu = true;
  #     wildmode = "longest:full";
  #     wildignore = [
  #       "*.o" "*~" "*.pyc" "*.pdb" "*.dll" "*.png"
  #       "__pycache__" "*.git" "*.hg" "*.svn" "node_modules"
  #     ];
  #
  #     # Status line
  #     statusline = "%f %m %r Line:%l/%L[%p%%] Col:%v Buf:#%n Char:[%b][0x%B]";
  #
  #     # System integration
  #     mouse = "a";
  #
  #     # Performance
  #     updatetime = 100;
  #     timeoutlen = 300;
  #   };
  #
  #   plugins = {
  #     # Enable web-devicons explicitly
  #     web-devicons.enable = true;
  #     notify = {
  #       enable = true;
  #     };
  #     # UI Enhancements
  #     # noice = {
  #     #   enable = true;
  #     #   settings.presets = {
  #     #     bottom_search = true;
  #     #     command_palette = true;
  #     #     long_message_to_split = true;
  #     #     inc_rename = true;
  #     #   };
  #     # };
  #
  #     # Smart splits
  #     smart-splits.enable = true;
  #
  #     # File Management
  #     oil = {
  #       enable = true;
  #       settings = {
  #         delete_to_trash = true;
  #         skip_confirm_for_simple_edits = true;
  #         keymaps = {
  #           "g?" = "actions.show_help";
  #           "<CR>" = "actions.select";
  #           "-" = "actions.parent";
  #           "_" = "actions.open_cwd";
  #           "`" = "actions.cd";
  #           "~" = "actions.tcd";
  #         };
  #       };
  #     };
  #
  #     # LSP and Completion
  #     lsp = {
  #       enable = true;
  #       servers = {
  #         clangd = {
  #           enable = true;
  #           cmd = ["clangd" "--background-index" "--clang-tidy"];
  #         };
  #         rust_analyzer = {
  #           enable = true;
  #           installCargo = true;
  #           installRustc = true;
  #         };
  #         nil_ls.enable = true;
  #         pyright = {
  #           enable = true;
  #           settings = {
  #             python = {
  #               analysis = {
  #                 typeCheckingMode = "basic";
  #                 autoSearchPaths = true;
  #                 useLibraryCodeForTypes = true;
  #                 diagnosticMode = "workspace";
  #               };
  #             };
  #           };
  #         };
  #       };
  #       keymaps = {
  #         diagnostic = {
  #           "<leader>j" = "goto_next";
  #           "<leader>k" = "goto_prev";
  #         };
  #         lspBuf = {
  #           "gd" = "definition";
  #           "gD" = "declaration";
  #           "K" = "hover";
  #           "<leader>rn" = "rename";
  #           "gr" = "references";
  #         };
  #       };
  #     };
  #
  #     none-ls = {
  #       enable = true;
  #       sources = {
  #         diagnostics = {
  #           mypy.enable = true;
  #         };
  #         formatting = {
  #           black.enable = true;
  #           isort.enable = true;
  #         };
  #       };
  #     };
  #
  #
  #     telescope = {
  #       enable = true;
  #       extensions.fzf-native.enable = true;
  #       settings = {
  #         defaults = {
  #           file_ignore_patterns = [".git/"];
  #           layout_config = {
  #             horizontal = {
  #               preview_cutoff = 120;
  #               preview_width = 0.6;
  #             };
  #           };
  #         };
  #       };
  #       keymaps = {
  #         "<leader><leader>" = "git_files";
  #         "<leader>fg" = "live_grep";
  #         "<leader>fb" = "buffers";
  #         "<leader>ff" = "find_files";
  #         "<leader>fh" = "help_tags";
  #         "<leader>B" = "oldfiles";
  #       };
  #     };
  #
  #     # Terminal
  #     toggleterm = {
  #       enable = true;
  #       settings = {
  #         direction = "float";
  #         float_opts = {
  #           border = "curved";
  #           winblend = 3;
  #         };
  #       };
  #     };
  #
  #     # Development Tools
  #     treesitter = {
  #       enable = true;
  #       settings.ensure_installed = [
  #         "c" "cpp" "rust" "python" "lua" "nix"
  #         "bash" "markdown" "regex" "markdown_inline"
  #         "toml" "json" "yaml" "cmake" "make"
  #         "vim"
  #       ];
  #     };
  #
  #     avante = {
  #       enable = true;
  #       settings = {
  #         provider = "claude";
  #         claude = {
  #           endpoint = "https://api.anthropic.com";
  #           model = "claude-3-5-sonnet-latest";
  #           temperature = 0;
  #           max_tokens = 8192;
  #         };
  #
  #         # Keyboard mappings
  #         mappings = {
  #           diff = {
  #             ours = "co";     # Choose our version
  #             theirs = "ct";   # Choose their version
  #             none = "c0";     # Choose neither
  #             both = "cb";     # Choose both
  #             next = "]x";     # Next difference
  #             prev = "[x";     # Previous difference
  #           };
  #         };
  #
  #         # Enable AI-powered hints
  #         hints.enabled = true;
  #
  #         # Window configuration
  #         windows = {
  #           wrap = true;      # Enable text wrapping
  #           width = 30;       # Sidebar width
  #           sidebar_header = {
  #             align = "center";
  #             rounded = true;
  #           };
  #         };
  #
  #         # Highlighting configuration
  #         highlights.diff = {
  #           current = "DiffText";
  #           incoming = "DiffAdd";
  #         };
  #
  #         # Diff settings
  #         diff = {
  #           debug = false;     # Disable debug mode
  #           autojump = true;   # Auto-jump to differences
  #           list_opener = "copen";  # Use quickfix list for differences
  #         };
  #       };
  #     };
  #   };
  #
  #   extraPlugins = with pkgs.vimPlugins; [
  #     dressing-nvim
  #     plenary-nvim
  #     nui-nvim
  #     nvim-web-devicons
  #     img-clip-nvim
  #     vim-expand-region
  #
  #     nvim-dap
  #     nvim-dap-python
  #     neotest
  #     neotest-python
  #     symbols-outline-nvim
  #   ];
  #
  #   extraPackages = with pkgs; [
  #     python3Packages.debugpy
  #     python3Packages.pytest
  #     python3Packages.black
  #     python3Packages.isort
  #     python3Packages.mypy
  #   ];
  #
  #   keymaps = [
  #     # Window Management
  #     { mode = "n"; key = "<C-j>"; action = "<C-W>j"; }
  #     { mode = "n"; key = "<C-k>"; action = "<C-W>k"; }
  #     { mode = "n"; key = "<C-h>"; action = "<C-W>h"; }
  #     { mode = "n"; key = "<C-l>"; action = "<C-W>l"; }
  #     { mode = "n"; key = "<C-m>"; action = "<C-W>_"; }
  #
  #     # Window Creation
  #     { mode = "n"; key = "<leader>v"; action = "<C-w>v<C-w>l"; }
  #     { mode = "n"; key = "<leader>V"; action = "<C-w>s<C-w>l"; }
  #
  #     # Terminal Navigation
  #     { mode = "t"; key = "<A-h>"; action = "<C-\\><C-N><C-w>h"; }
  #     { mode = "t"; key = "<A-j>"; action = "<C-\\><C-N><C-w>j"; }
  #     { mode = "t"; key = "<A-k>"; action = "<C-\\><C-N><C-w>k"; }
  #     { mode = "t"; key = "<A-l>"; action = "<C-\\><C-N><C-w>l"; }
  #     { mode = "i"; key = "<A-h>"; action = "<C-\\><C-N><C-w>h"; }
  #     { mode = "i"; key = "<A-j>"; action = "<C-\\><C-N><C-w>j"; }
  #     { mode = "i"; key = "<A-k>"; action = "<C-\\><C-N><C-w>k"; }
  #     { mode = "i"; key = "<A-l>"; action = "<C-\\><C-N><C-w>l"; }
  #
  #     # Line Manipulation
  #     { mode = "n"; key = "<C-Up>"; action = "ddkP"; }
  #     { mode = "n"; key = "<C-Down>"; action = "ddp"; }
  #     { mode = "v"; key = "<C-Up>"; action = "xkP`[V`]"; }
  #     { mode = "v"; key = "<C-Down>"; action = "xp`[V`]"; }
  #     { mode = "n"; key = "<leader><CR>"; action = "o<ESC>k"; }
  #
  #     # Clipboard Operations
  #     { mode = "n"; key = "<C-p>"; action = "o<ESC>\"+P"; }
  #     { mode = "v"; key = "<C-y>"; action = "\"+y"; }
  #
  #     # Quick Access
  #     { mode = "n"; key = "!"; action = ":!"; }
  #     { mode = "n"; key = "S"; action = ":%s/"; }
  #     { mode = "c"; key = "w!!"; action = "w !sudo tee >/dev/null %"; }
  #
  #     # Text Objects
  #     { mode = "v"; key = "v"; action = "<Plug>(expand_region_expand)"; }
  #     { mode = "v"; key = "V"; action = "<Plug>(expand_region_shrink)"; }
  #   ];
  #
  #   extraConfigLua = ''
  #     -- Expand region configuration
  #     vim.g.expand_region_text_objects = {
  #       ['i,w'] = 0,
  #       ['iw']  = 0,
  #       ['iW']  = 0,
  #       ['i"']  = 0,
  #       ["i'"]  = 0,
  #       ['ij']  = 1,
  #       ['ia']  = 0,
  #       ['il']  = 0,
  #       ['ip']  = 0,
  #       ['ii']  = 0,
  #       ['if']  = 0,
  #       ['ie']  = 0,
  #     }
  #
  #     -- LSP handlers configuration
  #     vim.lsp.handlers["textDocument/hover"] = vim.lsp.with(
  #       vim.lsp.handlers.hover, {
  #         border = "rounded",
  #         max_width = 80,
  #         max_height = 20,
  #       }
  #     )
  #
  #     -- Enable faster loading
  #     vim.loader.enable()
  #
  #     -- Set up additional keymaps for Avante
  #     vim.keymap.set('n', '<leader>aa', '<cmd>AvanteSuggest<CR>', { desc = 'Get AI suggestions' })
  #     vim.keymap.set('n', '<leader>ac', '<cmd>AvanteComplete<CR>', { desc = 'Complete with AI' })
  #     vim.keymap.set('v', '<leader>ae', '<cmd>AvanteExplain<CR>', { desc = 'Explain selected code' })
  #     vim.keymap.set('n', '<leader>ar', '<cmd>AvanteRefactor<CR>', { desc = 'Refactor code with AI' })
  #     vim.keymap.set('n', '<leader>at', '<cmd>AvanteTest<CR>', { desc = 'Generate tests with AI' })
  #
  #
  #     -- Set up symbols outline
  #     require('symbols-outline').setup({
  #       auto_close = true,
  #       position = 'right'
  #     })
  #
  #     -- Set up Python debugging
  #     require('dap-python').setup('.venv/bin/python')
  #
  #     -- Configure test runner
  #     require('neotest').setup({
  #       adapters = {
  #         require('neotest-python')({
  #           dap = { justMyCode = false },
  #           python = '.venv/bin/python',
  #           runner = 'pytest'
  #         })
  #       }
  #     })
  #
  #     -- Python-specific keymaps
  #     vim.api.nvim_create_autocmd("FileType", {
  #       pattern = "python",
  #       callback = function()
  #         -- Debug mappings
  #         vim.keymap.set("n", "<leader>db", ":lua require'dap'.toggle_breakpoint()<CR>", { buffer = true })
  #         vim.keymap.set("n", "<leader>dc", ":lua require'dap'.continue()<CR>", { buffer = true })
  #         vim.keymap.set("n", "<leader>ds", ":lua require'dap'.step_over()<CR>", { buffer = true })
  #         vim.keymap.set("n", "<leader>di", ":lua require'dap'.step_into()<CR>", { buffer = true })
  #
  #         -- Test mappings
  #         vim.keymap.set("n", "<leader>tt", ":lua require'neotest'.run.run()<CR>", { buffer = true })
  #         vim.keymap.set("n", "<leader>ts", ":lua require'neotest'.summary.toggle()<CR>", { buffer = true })
  #
  #         -- LSP enhanced mappings
  #         vim.keymap.set("n", "<leader>lf", ":lua vim.lsp.buf.format()<CR>", { buffer = true })
  #         vim.keymap.set("n", "<leader>li", ":lua require'telescope.builtin'.lsp_implementations()<CR>", { buffer = true })
  #
  #         -- Symbols outline
  #         vim.keymap.set("n", "<leader>so", ":SymbolsOutline<CR>", { buffer = true })
  #       end,
  #     })
  #
  #     -- Configure debugger for Hydrus
  #     local dap = require('dap')
  #     dap.configurations.python = {
  #       {
  #         type = 'python';
  #         request = 'launch';
  #         name = 'Launch Hydrus Client';
  #         program = './hydrus_client.py';
  #         args = {'--db_dir', './db/client'};
  #         pythonPath = function()
  #           return '.venv/bin/python'
  #         end;
  #       },
  #       {
  #         type = 'python';
  #         request = 'launch';
  #         name = 'Launch Hydrus Server';
  #         program = './hydrus_server.py';
  #         args = {'--db_dir', './db/server'};
  #         pythonPath = function()
  #           return '.venv/bin/python'
  #         end;
  #       }
  #     }
  #   '';
  # };
}
