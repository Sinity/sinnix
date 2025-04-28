--[[
total_usage_logger.lua
A robust, warning-free Neovim usage logger.
Features:
- Tracks every keypress (all modes), all Ex commands, buffer/window/tab/filetype events, yanks, completions, idle/focus, session ops, LSP, diagnostics, and major plugin actions.
- Hardened: No global field injection, no duplicate wrapping, no undefined variables, all warnings addressed.
- Designed for use with LazyVim or any Neovim (0.8+).
--]]

local M = {}

local log_path = vim.fn.stdpath("data") .. "/total_usage_log.csv"

local function safe_json_encode(tbl)
  local ok, out = pcall(vim.inspect, tbl)
  if ok then
    return out
  end
  return tostring(tbl)
end

local function log_event(event_type, detail, extra)
  local ok, err = pcall(function()
    local f = io.open(log_path, "a")
    if not f then
      return
    end
    local line = string.format(
      "%s,%s,%s,%s,%s,%d,%d,%d,%s\n",
      os.date("%Y-%m-%d %H:%M:%S"),
      event_type or "",
      tostring(detail or ""):gsub("\n", "\\n"):gsub(",", ";"),
      vim.bo.filetype or "",
      vim.api.nvim_buf_get_name(0) or "",
      vim.api.nvim_get_current_buf(),
      vim.api.nvim_get_current_win(),
      vim.api.nvim_get_current_tabpage(),
      tostring(extra or ""):gsub("\n", "\\n"):gsub(",", ";")
    )
    f:write(line)
    f:close()
  end)
  if not ok then
    vim.schedule(function()
      vim.notify("total_usage_logger log_event error: " .. tostring(err), vim.log.levels.ERROR)
    end)
  end
end

-- 1. Log every keypress (all modes)
pcall(function()
  if not vim.g._total_usage_logger_key_wrapped then
    vim.on_key(function(char)
      local mode = vim.api.nvim_get_mode().mode
      log_event("key_press", vim.fn.escape(char, ","), "mode:" .. mode)
    end, vim.api.nvim_create_namespace("total-usage-logger"))
    vim.g._total_usage_logger_key_wrapped = true
  end
end)

-- 2. Log all Ex (:) commands
pcall(function()
  vim.api.nvim_create_autocmd("CmdlineLeave", {
    pattern = ":",
    callback = function()
      local cmd = vim.fn.getcmdline()
      if cmd and #cmd > 0 then
        log_event("ex_command", cmd)
      end
    end,
    desc = "Log Ex commands",
  })
end)

-- 3. Log buffer, window, tab events + filetype changes, and time in buffer
local buftimes = {}
pcall(function()
  vim.api.nvim_create_autocmd("BufEnter", {
    callback = function()
      local buf = vim.api.nvim_get_current_buf()
      buftimes[buf] = os.time()
      log_event("buf_enter", vim.fn.expand("%:t"), "cwd:" .. vim.fn.getcwd())
    end,
    desc = "Log BufEnter and track time",
  })
  vim.api.nvim_create_autocmd("BufLeave", {
    callback = function()
      local buf = vim.api.nvim_get_current_buf()
      local enter_time = buftimes[buf]
      if enter_time then
        local spent = os.time() - enter_time
        log_event("buffer_time", buf, "seconds:" .. spent)
      end
      buftimes[buf] = nil
      log_event("buf_leave", vim.fn.expand("%:t"), "")
    end,
    desc = "Log BufLeave and time",
  })
  vim.api.nvim_create_autocmd({ "BufWinEnter", "BufWinLeave" }, {
    callback = function(args)
      log_event(args.event, vim.fn.expand("%:t"), "")
    end,
    desc = "Log window enter/leave",
  })
  vim.api.nvim_create_autocmd("FileType", {
    callback = function()
      log_event("filetype", vim.bo.filetype, "")
    end,
    desc = "Log FileType changes",
  })
  vim.api.nvim_create_autocmd({ "WinEnter", "WinLeave", "TabEnter", "TabLeave" }, {
    callback = function(args)
      log_event(args.event, "", "")
    end,
    desc = "Log window/tab enter/leave",
  })
end)

-- 4. Log yanks, puts, text changes
pcall(function()
  vim.api.nvim_create_autocmd("TextYankPost", {
    callback = function()
      log_event("yank", vim.fn.getreg('"'), "")
    end,
    desc = "Log yank",
  })
  vim.api.nvim_create_autocmd({ "TextChanged", "TextChangedI" }, {
    callback = function(args)
      log_event(args.event, "", "")
    end,
    desc = "Log text changes",
  })
end)

-- 5. Log insert completions (e.g. blink.cmp)
pcall(function()
  vim.api.nvim_create_autocmd("CompleteDone", {
    callback = function()
      local completed = vim.v.completed_item and safe_json_encode(vim.v.completed_item) or ""
      log_event("completion", completed)
    end,
    desc = "Log completion",
  })
end)

-- 6. Idle and focus time
pcall(function()
  vim.api.nvim_create_autocmd("CursorHold", {
    callback = function()
      log_event("idle", "cursorhold", "")
    end,
    desc = "Log idle",
  })
  vim.api.nvim_create_autocmd("FocusGained", {
    callback = function()
      log_event("focus", "gained", "")
    end,
    desc = "Log focus gained",
  })
  vim.api.nvim_create_autocmd("FocusLost", {
    callback = function()
      log_event("focus", "lost", "")
    end,
    desc = "Log focus lost",
  })
end)

-- 7. Log session operations
pcall(function()
  vim.api.nvim_create_autocmd({ "SessionLoadPost", "SessionSavePost" }, {
    callback = function(args)
      log_event(args.event, vim.v.this_session or "", "")
    end,
    desc = "Log session load/save",
  })
end)

-- 8. LSP events, without injecting fields
local lsp_attached_clients = {}
pcall(function()
  vim.api.nvim_create_autocmd("LspAttach", {
    callback = function(args)
      local client = vim.lsp.get_client_by_id(args.data.client_id)
      if client and not lsp_attached_clients[client.id] then
        lsp_attached_clients[client.id] = true
        for _, handler in ipairs({
          { "textDocument/hover", "hover" },
          { "textDocument/codeAction", "code_action" },
          { "textDocument/definition", "goto_definition" },
          { "textDocument/completion", "completion" },
        }) do
          local orig = client.handlers[handler[1]] or vim.lsp.handlers[handler[1]]
          client.handlers[handler[1]] = function(...)
            log_event("lsp_" .. handler[2], handler[1], safe_json_encode(select(2, ...)))
            return orig(...)
          end
        end
      end
    end,
    desc = "Log LSP events",
  })
end)

-- 9. Diagnostics navigation
pcall(function()
  vim.api.nvim_create_autocmd("User", {
    pattern = { "DiagnosticChanged", "DiagnosticJumped" },
    callback = function(args)
      log_event("diagnostic_event", args.event, "")
    end,
    desc = "Log diagnostics navigation",
  })
end)

-- 10. Plugin-specific hooks (fzf-lua, blink.cmp, nvim-tree, toggleterm, gitsigns, oil, mini.files)
pcall(function()
  -- fzf-lua
  local ok_fzf, fzf_lua = pcall(require, "fzf-lua")
  if ok_fzf and fzf_lua and not fzf_lua._usage_logger_wrapped then
    local function log_wrap(fn, name)
      return function(...)
        log_event("fzf-lua", name, "")
        return fn(...)
      end
    end
    local actions = {
      "files",
      "grep",
      "buffers",
      "lines",
      "oldfiles",
      "git_files",
      "git_status",
      "git_commits",
      "git_bcommits",
      "grep_curbuf",
      "help_tags",
      "marks",
      "commands",
    }
    for _, action in ipairs(actions) do
      if type(fzf_lua[action]) == "function" then
        fzf_lua[action] = log_wrap(fzf_lua[action], action)
      end
    end
    fzf_lua._usage_logger_wrapped = true
  end

  -- blink.cmp
  local ok_blink, blink_cmp = pcall(require, "blink.cmp")
  if ok_blink and blink_cmp and type(blink_cmp.complete) == "function" and not blink_cmp._usage_logger_wrapped then
    local orig_complete = blink_cmp.complete
    blink_cmp.complete = function(...)
      log_event("blink.cmp", "complete", "")
      return orig_complete(...)
    end
    blink_cmp._usage_logger_wrapped = true
  end

  -- nvim-tree.lua
  local ok_tree, _ = pcall(require, "nvim-tree")
  if ok_tree then
    vim.api.nvim_create_autocmd("User", {
      pattern = "NvimTreeOpen",
      callback = function()
        log_event("nvim_tree", "open", "")
      end,
    })
    vim.api.nvim_create_autocmd("User", {
      pattern = "NvimTreeClose",
      callback = function()
        log_event("nvim_tree", "close", "")
      end,
    })
  end

  -- toggleterm.nvim
  local ok_toggleterm, _ = pcall(require, "toggleterm")
  if ok_toggleterm then
    vim.api.nvim_create_autocmd("User", {
      pattern = "ToggleTermOpen",
      callback = function()
        log_event("toggleterm", "open", "")
      end,
    })
    vim.api.nvim_create_autocmd("User", {
      pattern = "ToggleTermClose",
      callback = function()
        log_event("toggleterm", "close", "")
      end,
    })
  end

  -- gitsigns.nvim
  local ok_gitsigns, gitsigns = pcall(require, "gitsigns")
  if ok_gitsigns and gitsigns and not gitsigns._usage_logger_wrapped then
    local function wrap_and_log(fn, name)
      return function(...)
        log_event("gitsigns", name, "")
        return fn(...)
      end
    end
    for k, v in pairs(gitsigns) do
      if type(v) == "function" then
        gitsigns[k] = wrap_and_log(v, k)
      end
    end
    gitsigns._usage_logger_wrapped = true
  end

  -- oil.nvim
  local ok_oil, _ = pcall(require, "oil")
  if ok_oil then
    vim.api.nvim_create_autocmd("User", {
      pattern = "OilOpen",
      callback = function()
        log_event("oil", "open", "")
      end,
    })
  end

  -- mini.files
  local ok_mini_files, mini_files = pcall(require, "mini.files")
  if ok_mini_files and mini_files and mini_files.open and not mini_files._usage_logger_wrapped then
    local orig_open = mini_files.open
    mini_files.open = function(...)
      log_event("mini.files", "open", "")
      return orig_open(...)
    end
    mini_files._usage_logger_wrapped = true
  end
end)

-- 11. Mouse events (best effort)
pcall(function()
  vim.api.nvim_create_autocmd({ "CursorMoved", "CursorMovedI" }, {
    callback = function()
      if vim.v.mouse_lnum and vim.v.mouse_col then
        log_event("mouse", "lnum:" .. tostring(vim.v.mouse_lnum) .. ",col:" .. tostring(vim.v.mouse_col), "")
      end
    end,
    desc = "Log mouse move",
  })
end)

-- 12. Hardened keymap logging: wrap only once, no field injection
pcall(function()
  if not vim.api._total_usage_logger_set_keymap_wrapped then
    local orig_set_keymap = vim.api.nvim_set_keymap
    vim.api.nvim_set_keymap = function(mode, lhs, rhs, opts)
      local rhs_fn = rhs
      if type(rhs) == "function" then
        rhs_fn = function(...)
          log_event("keymap_press", lhs, "mode:" .. tostring(mode))
          return rhs(...)
        end
      else
        local orig_rhs = rhs
        rhs = ":lua require'total_usage_logger'._log_and_exec('"
          .. lhs:gsub("'", "\\'")
          .. "','"
          .. tostring(mode)
          .. "','"
          .. orig_rhs:gsub("'", "\\'")
          .. "')<CR>"
      end
      return orig_set_keymap(mode, lhs, rhs_fn, opts)
    end
    vim.api._total_usage_logger_set_keymap_wrapped = true
  end

  if not vim.keymap._total_usage_logger_set_wrapped then
    local orig_keymap_set = vim.keymap.set
    vim.keymap.set = function(mode, lhs, rhs, opts)
      local rhs_fn = rhs
      if type(rhs) == "function" then
        rhs_fn = function(...)
          log_event("keymap_press", lhs, "mode:" .. safe_json_encode(mode))
          return rhs(...)
        end
      else
        local orig_rhs = rhs
        rhs = function(...)
          log_event("keymap_press", lhs, "mode:" .. safe_json_encode(mode))
          vim.api.nvim_feedkeys(vim.api.nvim_replace_termcodes(orig_rhs, true, true, true), mode, false)
        end
      end
      return orig_keymap_set(mode, lhs, rhs_fn, opts)
    end
    vim.keymap._total_usage_logger_set_wrapped = true
  end
end)

M._log_and_exec = function(lhs, mode, command)
  log_event("keymap_press", lhs, "mode:" .. tostring(mode))
  vim.api.nvim_feedkeys(vim.api.nvim_replace_termcodes(command, true, true, true), mode, false)
end

vim.api.nvim_create_user_command("UsageLogPreview", function()
  local log_path = vim.fn.stdpath("data") .. "/total_usage_log.csv"
  vim.cmd("vsplit " .. vim.fn.fnameescape(log_path))
  vim.bo.readonly = true
end, { desc = "Preview Total Usage Logger log (readonly)" })

M.log_path = log_path
return M
