--!nonstrict
-- Standing visibility for the reading stack: the count sits on the bar, the
-- newest entries and the cap warning live in the tooltip, and a click opens
-- the picker that consumes entries. The probe service publishes the stack
-- from its state file, so this widget only renders.

local SOFT_CAP = 20
local picker = noctalia.expandPath("~/.local/bin/sinnix-picker")

local stack = noctalia.state.get("sinnix-cockpit.reading-stack")

local function tooltipText()
  if type(stack) ~= "table" or stack.items == nil then
    return "Reading stack unavailable\nclick: open the picker"
  end
  local lines = {}
  if #stack.items == 0 then
    table.insert(lines, "Reading stack is empty")
  end
  for index, item in ipairs(stack.items) do
    if index > 12 then break end
    local title = item.title or item.url or "?"
    if #title > 60 then title = string.sub(title, 1, 59) .. "…" end
    table.insert(lines, title)
  end
  if stack.total > #stack.items then
    table.insert(lines, "… " .. tostring(stack.total - #stack.items) .. " more")
  end
  if stack.total > SOFT_CAP then
    table.insert(lines, tostring(stack.total) .. " total, over the soft cap of " .. tostring(SOFT_CAP) .. ": review")
  end
  table.insert(lines, "click: choose one in the picker (SUPER+O)")
  return table.concat(lines, "\n")
end

local function render()
  local known = type(stack) == "table" and stack.total ~= nil
  local color = "on_surface_variant"
  if known and stack.total > SOFT_CAP then
    color = "error"
  elseif known and stack.total > 0 then
    color = "on_surface"
  end
  local children = { ui.glyph({ name = "menu_book", size = 14, color = color }) }
  if known and stack.total > 0 then
    table.insert(children, ui.label({ text = tostring(stack.total), color = color }))
  end
  barWidget.setTooltip(tooltipText())
  barWidget.render(ui.row({ gap = 4, align = "center" }, children))
end

function onClick()
  if not noctalia.runAsync("uwsm app -- " .. picker) then
    noctalia.notifyError("Could not open the picker")
  end
end

noctalia.state.watch("sinnix-cockpit.reading-stack", function(value)
  stack = value
  render()
end)

function update()
  render()
end
