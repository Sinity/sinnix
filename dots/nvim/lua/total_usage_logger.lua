-- total_usage_logger.lua
-- Slimmed, signal-rich Neovim usage logger:
-- - Collapses key bursts (e.g. multiple j/g in normal mode)
-- - Only logs significant events: mode, buffer, filetype, cwd, commands, file save, (optionally) >1s idle
-- - Robust monotonic timer fallback (works even if vim.loop.hrtime unavailable)
-- - Redundant/rapid events deduped

local M = {}

-- CONFIG
local log_file = vim.fn.stdpath("data") .. "/usage_log.csv"
local burst_timeout = 0.7 -- seconds for burst grouping
local min_burst = 2 -- minimum count to log as burst
local idle_min_seconds = 1.0 -- only log idle if >= this many seconds

-- STATE
local last_ctx = { buf = nil, ft = nil, cwd = nil }
local key_burst = { key = nil, mode = nil, count = 0, start = nil, last = nil }
local idle_start_wall, idle_start_mon
local last_mode, last_filetype, last_cwd, last_buf

-- Monotonic timer, fallback for Lua without vim.loop.hrtime
local uv = vim.loop
local function now_monotonic()
  if uv and type(uv.hrtime) == "function" then
    return uv.hrtime() / 1e9
  end
  return os.clock()
end

local function write_log(...)
  local f = io.open(log_file, "a")
  if not f then
    return
  end
  local cells = { os.date("%Y-%m-%d %H:%M:%S") }
  for _, v in ipairs({ ... }) do
    table.insert(cells, tostring(v))
  end
  f:write(table.concat(cells, ",") .. "\n")
  f:close()
end

local function flush_key_burst()
  if key_burst.count >= min_burst then
    write_log(
      "key_burst",
      key_burst.key,
      key_burst.mode,
      "count=" .. key_burst.count,
      string.format("dur=%.3f", key_burst.last - key_burst.start)
    )
  elseif key_burst.count > 0 then
    -- log as individual
    for _ = 1, key_burst.count do
      write_log("key_press", key_burst.key, key_burst.mode)
    end
  end
  key_burst = { key = nil, mode = nil, count = 0, start = nil, last = nil }
end

local function flush_idle()
  if idle_start_wall and idle_start_mon then
    local end_wall = os.time()
    local end_mon = now_monotonic()
    local dur = end_mon - idle_start_mon
    if dur >= idle_min_seconds then
      write_log(
        "idle_period",
        "start=" .. os.date("%Y-%m-%d %H:%M:%S", idle_start_wall),
        "end=" .. os.date("%Y-%m-%d %H:%M:%S", end_wall),
        string.format("dur=%.3f", dur)
      )
    end
    idle_start_wall, idle_start_mon = nil, nil
  end
end

local function log_context(force)
  -- Buffer
  local buf = vim.api.nvim_get_current_buf()
  if buf ~= last_buf or force then
    local name = vim.api.nvim_buf_get_name(buf)
    write_log("buffer_open", name)
    last_buf = buf
  end
  -- Filetype
  local ft = vim.bo[buf].filetype or ""
  if ft ~= last_filetype or force then
    write_log("filetype_changed", ft)
    last_filetype = ft
  end
  -- CWD
  local cwd = vim.fn.getcwd()
  if cwd ~= last_cwd or force then
    write_log("cwd_change", cwd)
    last_cwd = cwd
  end
end

-- KEY BURST LOGIC
vim.on_key(function(char)
  local now = now_monotonic()
  local mode = vim.api.nvim_get_mode().mode
  -- burst timeout or change
  if key_burst.last and (now - key_burst.last > burst_timeout or key_burst.key ~= char or key_burst.mode ~= mode) then
    flush_key_burst()
  end
  -- new burst or extend
  if not key_burst.key or key_burst.key ~= char or key_burst.mode ~= mode then
    key_burst.key, key_burst.mode = char, mode
    key_burst.start, key_burst.count = now, 1
  else
    key_burst.count = key_burst.count + 1
  end
  key_burst.last = now

  -- mark activity (end idle)
  if idle_start_mon then
    flush_idle()
  end
  log_context(false)
end, vim.api.nvim_create_namespace("usage-logger"))

-- TIMER for burst flush
vim.fn.timer_start(math.floor(burst_timeout * 1000), function()
  if key_burst.last and now_monotonic() - key_burst.last > burst_timeout then
    flush_key_burst()
  end
end, { ["repeat"] = -1 })

-- MODE CHANGE
vim.api.nvim_create_autocmd("ModeChanged", {
  callback = function(args)
    flush_key_burst()
    if args.match ~= last_mode then
      write_log("mode_change", args.match)
      last_mode = args.match
    end
  end,
})

-- EX COMMAND EXECUTION
vim.api.nvim_create_autocmd("CmdlineLeave", {
  callback = function()
    local cmd = vim.fn.getcmdline()
    if cmd ~= "" then
      write_log("ex_command", cmd)
      flush_key_burst()
    end
  end,
})

-- BUFFER OPEN/CLOSE
vim.api.nvim_create_autocmd({ "BufReadPost", "BufNewFile" }, {
  callback = function()
    log_context(true)
  end,
})
vim.api.nvim_create_autocmd("BufUnload", {
  callback = function()
    write_log("buffer_close", vim.fn.expand("<abuf>"))
  end,
})

-- FILE SAVE
vim.api.nvim_create_autocmd("BufWritePost", {
  callback = function()
    write_log("file_save", vim.api.nvim_buf_get_name(0))
  end,
})

-- CWD CHANGE
vim.api.nvim_create_autocmd("DirChanged", {
  callback = function()
    write_log("cwd_change", vim.fn.getcwd())
  end,
})

-- FILETYPE CHANGE
vim.api.nvim_create_autocmd("FileType", {
  callback = function()
    local ft = vim.bo[vim.api.nvim_get_current_buf()].filetype
    if ft ~= last_filetype then
      write_log("filetype_changed", ft)
      last_filetype = ft
    end
  end,
})

-- WINDOW & TAB CREATION
vim.api.nvim_create_autocmd("WinNew", {
  callback = function()
    write_log("win_new")
  end,
})
vim.api.nvim_create_autocmd("TabNew", {
  callback = function()
    write_log("tab_new")
  end,
})

-- IDLE SUMMARIZATION (CursorHold triggers after updatetime, default 4s; user may want to lower it)
vim.api.nvim_create_autocmd("CursorHold", {
  callback = function()
    if not idle_start_mon then
      idle_start_wall = os.time()
      idle_start_mon = now_monotonic()
    end
    flush_key_burst()
  end,
})

-- USER COMMAND to view log
vim.api.nvim_create_user_command("UsageLog", function()
  vim.cmd("tabnew " .. vim.fn.fnameescape(log_file))
end, { desc = "Open usage log CSV" })

return M
