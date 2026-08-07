--!nonstrict
-- Read-only Now panel for the Sinnix operations snapshot.

local view = noctalia.state.get("sinity-ops.view") or { status = "disconnected" }

local function text(value)
  if value == nil then return "unavailable" end
  return tostring(value)
end

local function compact(value)
  if value == nil then return "unavailable" end
  if type(value) ~= "table" then return tostring(value) end
  if value.status ~= nil then return tostring(value.status) end
  if value.available ~= nil then return value.available and "available" or "unavailable" end
  if value.healthy ~= nil then return value.healthy and "healthy" or "unhealthy" end
  return "reported"
end

local function stateValue(name)
  if type(view.snapshot) ~= "table" or type(view.snapshot.state) ~= "table" then return nil end
  return view.snapshot.state[name]
end

local function pressureText()
  local pressure = stateValue("live_pressure")
  if type(pressure) ~= "table" then return "unavailable" end
  local memory = pressure.memory and pressure.memory.some and pressure.memory.some.avg10
  local io = pressure.io and pressure.io.some and pressure.io.some.avg10
  return "memory PSI " .. text(memory) .. ", IO PSI " .. text(io)
end

local function gapText()
  local gaps = stateValue("gaps_summary")
  if type(gaps) ~= "table" then return "unavailable" end
  local count = 0
  for _ in pairs(gaps) do count = count + 1 end
  return tostring(count) .. " gap classes"
end

local function incidentText()
  local tasks = stateValue("blocked_tasks")
  if type(tasks) ~= "table" then return "unavailable" end
  return tostring(#tasks) .. " blocked tasks"
end

local function render()
  local rows = {
    ui.label({ text = "Sinnix operations", fontSize = 18, fontWeight = "bold", color = "primary" }),
    ui.label({ text = "Connection: " .. text(view.status) .. "  Source: " .. text(view.source), color = view.status == "connected" and "primary" or "error" }),
    ui.label({ text = "Reason: " .. text(view.reason), color = "on_surface_variant" }),
    ui.column({ gap = 6, padding = 10, fill = "surface_variant/0.4", radius = 8 }, {
      ui.label({ text = "Pressure and memory: " .. pressureText(), color = "on_surface" }),
      ui.label({ text = "GPU: " .. compact(stateValue("gpu")), color = "on_surface" }),
      ui.label({ text = "Heavy lease: " .. compact(stateValue("runtime_inventory")), color = "on_surface" }),
      ui.label({ text = "Drift: " .. gapText(), color = "on_surface" }),
      ui.label({ text = "Backup and capture: " .. compact(stateValue("storage")), color = "on_surface" }),
      ui.label({ text = "Incidents: " .. incidentText(), color = "on_surface" }),
    }),
    ui.label({ text = "Read-only. Data expires after the configured freshness window.", color = "on_surface_variant", fontSize = 12 }),
  }
  panel.render(ui.column({ gap = 12, padding = 16 }, rows))
end

noctalia.state.watch("sinity-ops.view", function(value)
  view = type(value) == "table" and value or { status = "disconnected" }
  render()
end)

function onOpen(_context)
  render()
end
