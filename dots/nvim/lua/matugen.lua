 local M = {}

function M.setup()
  require('base16-colorscheme').setup({
    base00 = '#131314',
    base01 = '#1f2020',
    base02 = '#2a2a2a',
    base03 = '#8d9193',
    base04 = '#c3c7c9',
    base05 = '#e4e2e2',
    base06 = '#e4e2e2',
    base07 = '#e4e2e2',
    base08 = '#ffb4ab',
    base09 = '#cdc3d0',
    base0A = '#c4c7c9',
    base0B = '#bdc8cd',
    base0C = '#cdc3d0',
    base0D = '#bdc8cd',
    base0E = '#c4c7c9',
    base0F = '#93000a',
  })

  local hi = function(group, opts)
    vim.api.nvim_set_hl(0, group, opts)
  end

  hi('TelescopeNormal',         { fg = '#e4e2e2',          bg = '#131314' })
  hi('TelescopeBorder',         { fg = '#8d9193',             bg = '#131314' })
  hi('TelescopePromptNormal',   { fg = '#e4e2e2',          bg = '#131314' })
  hi('TelescopePromptBorder',   { fg = '#8d9193',             bg = '#131314' })
  hi('TelescopePromptPrefix',   { fg = '#bdc8cd',             bg = '#131314' })
  hi('TelescopePromptCounter',  { fg = '#c3c7c9',  bg = '#131314' })
  hi('TelescopePromptTitle',    { fg = '#131314',             bg = '#bdc8cd' })
  hi('TelescopePreviewTitle',   { fg = '#131314',             bg = '#c4c7c9' })
  hi('TelescopeResultsTitle',   { fg = '#131314',             bg = '#cdc3d0' })
  hi('TelescopeSelection',      { fg = '#e4e2e2',          bg = '#2a2a2a' })
  hi('TelescopeSelectionCaret', { fg = '#bdc8cd',             bg = '#2a2a2a' })
  hi('TelescopeMatching',       { fg = '#bdc8cd',             bold = true })
end

 -- Re-apply colors on matugen's SIGUSR1. Register the uv watcher EXACTLY ONCE,
 -- guarded by a global. The handler still resets the cache + re-requires so a
 -- freshly-rendered palette is picked up, but the guard stops that reload from
 -- re-running this block and starting ANOTHER watcher. Without the guard every
 -- signal leaked a new uv signal handle (1->2->4->... live watchers, each
 -- pinning an un-GC'd module reload) -- exponential under Noctalia's frequent
 -- palette updates, ballooning each nvim to multiple GiB.
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
