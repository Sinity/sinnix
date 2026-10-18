--!nonstrict
-- Capability index entry point: the whole declared surface one click away.
-- Shows the row count from /etc/sinnix/capability-index.json (read by the
-- probe service, refreshed on mtime change — the file only moves on switch),
-- per-kind counts in the tooltip, and a click lists every capability with how
-- to invoke it (`sinnix capabilities`) in a terminal.

local LIST_COMMAND = "kitty --title 'Sinnix capabilities' sh -c 'sinnix capabilities | less -R'"

local caps = noctalia.state.get("sinnix-bar.capabilities")

local function tooltipText()
  if type(caps) ~= "table" or caps.total == nil then
    return "Capability index unavailable\nclick: list capabilities in a terminal"
  end
  local lines = { tostring(caps.total) .. " declared capabilities" }
  local names = {}
  for kind in pairs(caps.kinds or {}) do
    table.insert(names, kind)
  end
  table.sort(names)
  for _, kind in ipairs(names) do
    table.insert(lines, "  " .. kind .. ": " .. tostring(caps.kinds[kind]))
  end
  table.insert(lines, "click: list capabilities in a terminal")
  return table.concat(lines, "\n")
end

local function render()
  local known = type(caps) == "table" and caps.total ~= nil
  local color = known and "on_surface" or "on_surface_variant"
  local children = { ui.glyph({ name = "apps", size = 14, color = color }) }
  if known then
    table.insert(children, ui.label({ text = tostring(caps.total), color = color }))
  end
  barWidget.setTooltip(tooltipText())
  barWidget.render(ui.row({ gap = 4, align = "center" }, children))
end

function onClick()
  if not noctalia.runAsync(LIST_COMMAND) then
    noctalia.notifyError("Could not open the capability list")
  end
end

noctalia.state.watch("sinnix-bar.capabilities", function(value)
  caps = value
  render()
end)

function update()
  render()
end
