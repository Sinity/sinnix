--!nonstrict
-- Capability index entry point: the whole declared surface one click away.
-- Shows the row count from /etc/sinnix/capability-index.json (read by the
-- probe service, refreshed on mtime change — the file only moves on switch),
-- per-kind counts in the tooltip, and a click opens the hub's /capabilities/
-- page, which joins the same index with live health and census usage.

local HUB_URL = noctalia.getConfig("hub_url") or "http://127.0.0.1:8880"

local caps = noctalia.state.get("sinnix-cockpit.capabilities")

local function tooltipText()
  if type(caps) ~= "table" or caps.total == nil then
    return "Capability index unavailable\nclick: open the hub capabilities page"
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
  table.insert(lines, "click: open the hub capabilities page")
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
  if not noctalia.runAsync("xdg-open '" .. HUB_URL .. "/capabilities/'") then
    noctalia.notifyError("Could not open " .. HUB_URL .. "/capabilities/")
  end
end

noctalia.state.watch("sinnix-cockpit.capabilities", function(value)
  caps = value
  render()
end)

function update()
  render()
end
