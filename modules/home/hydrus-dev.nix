# modules/home/hydrus-dev.nix
{ config, pkgs, ... }:

{
  programs.nixvim = {
    plugins = {
      # Language specific enhancements
      none-ls = {
        enable = true;
        sources = {
          diagnostics = {
            mypy.enable = true;
          };
          formatting = {
            black.enable = true;
            isort.enable = true;
          };
        };
      };

      # LSP configuration
      lsp.servers = {
        pyright = {
          enable = true;
          settings = {
            python = {
              analysis = {
                typeCheckingMode = "basic";
                autoSearchPaths = true;
                useLibraryCodeForTypes = true;
                diagnosticMode = "workspace";
              };
            };
          };
        };
      };
    };

    extraPlugins = with pkgs.vimPlugins; [
      nvim-dap
      nvim-dap-python
      neotest
      neotest-python
      symbols-outline-nvim
    ];

    extraConfigLua = ''
      -- Set up symbols outline
      require('symbols-outline').setup({
        auto_close = true,
        position = 'right'
      })
      
      -- Set up Python debugging
      require('dap-python').setup('.venv/bin/python')
      
      -- Configure test runner
      require('neotest').setup({
        adapters = {
          require('neotest-python')({
            dap = { justMyCode = false },
            python = '.venv/bin/python',
            runner = 'pytest'
          })
        }
      })

      -- Python-specific keymaps
      vim.api.nvim_create_autocmd("FileType", {
        pattern = "python",
        callback = function()
          -- Debug mappings
          vim.keymap.set("n", "<leader>db", ":lua require'dap'.toggle_breakpoint()<CR>", { buffer = true })
          vim.keymap.set("n", "<leader>dc", ":lua require'dap'.continue()<CR>", { buffer = true })
          vim.keymap.set("n", "<leader>ds", ":lua require'dap'.step_over()<CR>", { buffer = true })
          vim.keymap.set("n", "<leader>di", ":lua require'dap'.step_into()<CR>", { buffer = true })
          
          -- Test mappings
          vim.keymap.set("n", "<leader>tt", ":lua require'neotest'.run.run()<CR>", { buffer = true })
          vim.keymap.set("n", "<leader>ts", ":lua require'neotest'.summary.toggle()<CR>", { buffer = true })
          
          -- LSP enhanced mappings
          vim.keymap.set("n", "<leader>lf", ":lua vim.lsp.buf.format()<CR>", { buffer = true })
          vim.keymap.set("n", "<leader>li", ":lua require'telescope.builtin'.lsp_implementations()<CR>", { buffer = true })
          
          -- Symbols outline
          vim.keymap.set("n", "<leader>so", ":SymbolsOutline<CR>", { buffer = true })
        end,
      })

      -- Configure debugger for Hydrus
      local dap = require('dap')
      dap.configurations.python = {
        {
          type = 'python';
          request = 'launch';
          name = 'Launch Hydrus Client';
          program = './hydrus_client.py';
          args = {'--db_dir', './db/client'};
          pythonPath = function()
            return '.venv/bin/python'
          end;
        },
        {
          type = 'python';
          request = 'launch';
          name = 'Launch Hydrus Server';
          program = './hydrus_server.py';
          args = {'--db_dir', './db/server'};
          pythonPath = function()
            return '.venv/bin/python'
          end;
        }
      }
    '';

    extraPackages = with pkgs; [
      python3Packages.debugpy
      python3Packages.pytest
      python3Packages.black
      python3Packages.isort
      python3Packages.mypy
    ];
  };
}
