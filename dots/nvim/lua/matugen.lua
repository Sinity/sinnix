local M = {}

function M.setup()
  local state = vim.env.XDG_STATE_HOME or (vim.env.HOME .. '/.local/state')
  local generated_path = state .. '/noctalia/nvim/matugen.lua'
  local ok, generated = pcall(dofile, generated_path)
  if ok and type(generated) == 'table' and type(generated.setup) == 'function' then
    generated.setup()
  end
end

-- Re-apply colors on Noctalia's SIGUSR1. Register the uv watcher exactly once,
-- guarded by a global. Without the guard, module reloads can leak another
-- watcher and make later palette updates fan out recursively.
if not _G.__matugen_signal then
  _G.__matugen_signal = vim.uv.new_signal()
  _G.__matugen_signal:start(
    'sigusr1',
    vim.schedule_wrap(function()
      package.loaded['matugen'] = nil
      require('matugen').setup()
    end)
  )
end

return M
