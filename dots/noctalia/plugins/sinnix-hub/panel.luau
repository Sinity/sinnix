--!nonstrict
-- Sinnix operations panel: the glanceable read of the hub server snapshot.
--
-- Every rendered line is a real number or state from the live snapshot;
-- anything the hub server cannot provide says so with its reason instead of a
-- placeholder. Deep views belong to the hub pages -- the link row at the
-- bottom opens them -- so this panel stays a summary, not a second hub.
--
-- State access rule: snapshot state is read only through stateValue with a
-- literal key name. The noctalia-hub-bridge flake check parses those
-- literals and fails when a bound key is not published by the hub server's
-- snapshot-building code, so a schema drift cannot silently render junk.

local HUB_URL = noctalia.getConfig("hub_url") or "http://127.0.0.1:8880"

local view = noctalia.state.get("sinity-hub.view") or { status = "disconnected" }

local function text(value)
  if value == nil then return "?" end
  return tostring(value)
end

local function stateValue(name)
  if type(view.snapshot) ~= "table" or type(view.snapshot.state) ~= "table" then return nil end
  local sections = view.snapshot.sections
  local section = type(sections) == "table" and sections[name]
  if type(section) == "table" and section.available == false then return nil end
  return view.snapshot.state[name]
end

local function sourceHealth(name)
  if type(view.snapshot) ~= "table" or type(view.snapshot.sources) ~= "table" then return nil end
  local value = view.snapshot.sources[name]
  if type(value) ~= "table" then return nil end
  return value
end

local function pct(value)
  if type(value) ~= "number" then return "?" end
  return string.format("%.1f%%", value)
end

-- ## Now: pressure, memory, stalls ##

local function pressureText()
  local pressure = stateValue("live_pressure")
  if type(pressure) ~= "table" then return "PSI: unavailable (no live_pressure in snapshot)" end
  local function some(name)
    local lane = pressure[name]
    if type(lane) ~= "table" or type(lane.some) ~= "table" then return "?" end
    return pct(lane.some.avg10)
  end
  return "PSI some avg10: cpu " .. some("cpu") .. ", memory " .. some("memory") .. ", io " .. some("io")
end

local function memoryText()
  local pressure = stateValue("live_pressure")
  local free = type(pressure) == "table" and pressure.free_h
  if type(free) ~= "string" then return "Memory: unavailable (no free output in snapshot)" end
  local total, _, available = free:match("Mem:%s+(%S+)%s+(%S+)%s+%S+%s+%S+%s+%S+%s+(%S+)")
  local swapTotal, swapUsed = free:match("Swap:%s+(%S+)%s+(%S+)")
  if total == nil then return "Memory: unavailable (free output unrecognized)" end
  local line = "Memory: " .. available .. " available of " .. total
  if swapTotal ~= nil then line = line .. "; swap " .. swapUsed .. " of " .. swapTotal .. " used" end
  return line
end

-- ## Fleet: units, drift, gaps, governance ##

local function unitsLines()
  local units = stateValue("systemd_units")
  if type(units) ~= "table" then return { "Units: unavailable (no systemd_units in snapshot)" } end
  local active, failed, failedNames = 0, 0, {}
  for _, unit in ipairs(units) do
    if unit.active_state == "active" then active = active + 1 end
    if unit.active_state == "failed" then
      failed = failed + 1
      if #failedNames < 3 then table.insert(failedNames, text(unit.unit)) end
    end
  end
  local lines = { "Units: " .. tostring(active) .. " active, " .. tostring(failed) .. " failed of " .. tostring(#units) .. " observed" }
  if failed > 0 then table.insert(lines, "  failed: " .. table.concat(failedNames, ", ")) end
  return lines
end

local function governanceText()
  local inventory = stateValue("runtime_inventory")
  if type(inventory) ~= "table" then return "Governance: unavailable (no runtime_inventory in snapshot)" end
  local units = 0
  if type(inventory.units) == "table" then
    for _ in pairs(inventory.units) do units = units + 1 end
  end
  local captures = type(inventory.captures) == "table" and #inventory.captures or 0
  return "Governance: " .. tostring(units) .. " units, " .. tostring(captures) .. " capture lanes, " .. tostring(sliceCount) .. " slices live"
end

-- ## Agents: owner queue snapshot ##

local function agentLines()
  local health = sourceHealth("agentctl")
  local snapshot = stateValue("agentctl")
  if type(snapshot) ~= "table" then
    local reason = health ~= nil and (" -- " .. text(health.degradation)) or ""
    return { "Jobs: unavailable" .. reason }
  end
  local coverage = type(snapshot.coverage) == "table" and snapshot.coverage or {}
  local active = type(coverage.active) == "table" and coverage.active or {}
  local omitted = type(snapshot.omitted) == "table" and snapshot.omitted or {}
  local lines = { "Jobs: " .. text(active.returned) .. "/" .. text(active.total) .. " active rows, " .. text(omitted.terminal) .. " terminal rows omitted" }
  local groups = type(snapshot.groups) == "table" and snapshot.groups or {}
  for name, group in pairs(groups) do
    if type(group) == "table" then
      table.insert(lines, "  " .. tostring(name) .. ": " .. text(group.status) .. ", " .. text(group.running) .. " running, " .. text(group.queued) .. " queued")
    end
  end
  local jobs = type(snapshot.jobs) == "table" and snapshot.jobs or {}
  for index = 1, math.min(#jobs, 4) do
    local job = jobs[index]
    if type(job) == "table" then
      table.insert(lines, "  " .. text(job.label) .. ": " .. text(job.phase) .. " · job " .. text(job.job_id) .. " · attempt " .. text(job.attempt))
    end
  end
  return lines
end

-- ## Signals: ambient product, AFK anchor, receipts ##

local function ambientLines()
  local health = sourceHealth("ambient-intelligence")
  local ambient = stateValue("ambient_intelligence")
  if type(ambient) == "table" then
    local fragmentation = ambient.fragmentation or {}
    local anomalies = ambient.anomalies or {}
    local chores = ambient.chores or {}
    return {
      "Ambient: fragmentation " .. text(fragmentation.risk) .. ", " .. tostring(#anomalies) .. " anomalies, " .. tostring(#chores) .. " chores",
    }
  end
  if health ~= nil then
    return { "Ambient: " .. text(health.status) .. " -- " .. text(health.degradation) }
  end
  return { "Ambient: unavailable (no ambient-intelligence source in snapshot)" }
end

local function anchorText()
  local anchor = stateValue("session_anchor")
  if type(anchor) ~= "table" then
    -- The hub server publishes an anchor only for 1h after an AFK gap of 30min
    -- or more, so nil is the normal steady state, not a failure.
    return "AFK return: no recent AFK interval"
  end
  local brief = anchor.brief or {}
  return "AFK return: " .. text(brief.focused_project) .. ", " .. tostring(#(brief.recent_commits or {})) .. " commit refs, " .. tostring(#(brief.resumable_agents or {})) .. " agent refs"
end

local function receiptText()
  if type(view.receipts) ~= "table" or type(view.receipts.receipts) ~= "table" then
    return "Action receipts: unavailable (receipts endpoint not read yet)"
  end
  local receipts = view.receipts.receipts
  if #receipts == 0 then return "Action receipts: none recorded" end
  local latest = receipts[#receipts]
  return "Action receipts: " .. tostring(#receipts) .. " recent, latest " .. text(latest.action) .. " " .. text(latest.adapter and latest.adapter.status)
end

-- ## Layout ##

local function infoSection(title, lines)
  local children = { ui.label({ text = title, fontWeight = "bold", color = "primary" }) }
  for _, line in ipairs(lines) do
    table.insert(children, ui.label({ text = line, color = "on_surface" }))
  end
  return ui.column({ gap = 4, padding = 8, fill = "surface_variant/0.25", radius = 6 }, children)
end

local function hubButton(label, path, tooltip)
  return ui.button({
    text = label,
    variant = "outline",
    controlSize = "sm",
    tooltip = tooltip,
    onClick = function()
      if not noctalia.runAsync("xdg-open '" .. HUB_URL .. path .. "'") then
        noctalia.notifyError("Could not open the hub at " .. HUB_URL .. path)
      end
    end,
  })
end

-- Pins live only for this panel process. Refresh never replaces a saved pin.
local work = { rows = {}, gaps = { "Work destinations not read yet" } }
local pins = {}
local workRequest = 0
local workBusy = false
local render

local function workHttp(path, pin, callback)
  local runtime = noctalia.getenv("XDG_RUNTIME_DIR") or ""
  local tokenPath = noctalia.getConfig("token_path") or "$XDG_RUNTIME_DIR/sinnix/hub.token"
  local token = noctalia.readFile(noctalia.expandPath(tokenPath:gsub("%$XDG_RUNTIME_DIR", runtime)))
  if token == nil then callback(nil); return end
  local options = {
    url = (noctalia.getConfig("endpoint") or "http://127.0.0.1:3090") .. path,
    headers = { "Authorization: Bearer " .. token:gsub("%s+$", ""), "Content-Type: application/json" },
  }
  if pin ~= nil then options.method = "POST"; options.body = noctalia.json.encode({ pin = pin }) end
  local admitted = noctalia.http(options, function(response)
    local ok, value = pcall(noctalia.json.decode, response.body or "")
    callback(response.ok and response.status == 200 and ok and value or nil)
  end)
  if admitted == false then callback(nil) end
end

local function refreshWork()
  if workBusy then return end
  workBusy = true
  workRequest = workRequest + 1
  local request = workRequest
  workHttp("/v1/work", nil, function(value)
    if request ~= workRequest then return end
    workBusy = false
    work = type(value) == "table" and value or { rows = {}, gaps = { "Work source unavailable; saved pins unverified" } }
    render()
  end)
end

local function pinKey(pin)
  return pin.kind .. ":" .. (pin.endpoint or "") .. ":" .. pin.id
end

local function workSection()
  local children = { ui.label({ text = "Work", fontWeight = "bold", color = "primary" }) }
  local current = {}
  for _, row in ipairs(work.rows or {}) do
    local key = pinKey(row.pin)
    current[key] = row
    if pins[key] == nil then pins[key] = row end
  end
  for key, saved in pairs(pins) do
    local row = current[key]
    local same = row ~= nil and (row.pin.epoch == saved.pin.epoch and row.pin.url == saved.pin.url)
    if same then saved = row end
    local pin = saved.pin
    table.insert(children, ui.label({ text = saved.name .. " · " .. saved.state, color = "on_surface" }))
    table.insert(children, ui.label({ text = (saved.detail or "") .. " · pin " .. pin.id .. " · " .. (same and "observed" or "stale/unverified; rebind required"), color = "on_surface_variant" }))
    local buttons = {
      ui.button({ text = "Focus exact pin", variant = "outline", controlSize = "sm", onClick = function()
        workHttp("/v1/work/focus", pin, function(value)
          if value == nil then noctalia.notifyError("Destination stale/unverified or focus failed. Refresh and rebind explicitly.") end
        end)
      end }),
    }
    if row ~= nil and not same then
      local replacement = row
      table.insert(buttons, ui.button({ text = "Rebind to current", variant = "outline", controlSize = "sm", onClick = function() pins[key] = replacement; render() end }))
    end
    table.insert(children, ui.row({ gap = 6 }, buttons))
  end
  for _, gap in ipairs(work.gaps or {}) do table.insert(children, ui.label({ text = gap, color = "on_surface_variant" })) end
  if (work.omitted or 0) > 0 then table.insert(children, ui.label({ text = tostring(work.omitted) .. " destinations omitted" })) end
  table.insert(children, ui.button({ text = "Refresh destinations", onClick = refreshWork }))
  return ui.column({ gap = 4, padding = 8, fill = "surface_variant/0.25", radius = 6 }, children)
end

render = function()
  local rows = {
    ui.label({ text = "Sinnix operations", fontSize = 18, fontWeight = "bold", color = "primary" }),
    ui.label({
      text = "Connection: " .. text(view.status) .. " via " .. text(view.source),
      color = view.status == "connected" and "primary" or "error",
    }),
  }
  if view.reason ~= nil then
    table.insert(rows, ui.label({ text = "Reason: " .. text(view.reason), color = "on_surface_variant" }))
  end
  table.insert(rows, infoSection("Now", { pressureText(), memoryText() }))
  local fleet = unitsLines()
  table.insert(fleet, governanceText())
  table.insert(rows, infoSection("Fleet", fleet))
  local agents = {}
  for _, line in ipairs(agentLines()) do table.insert(agents, line) end
  table.insert(rows, infoSection("Agents", agents))
  table.insert(rows, workSection())
  local signals = ambientLines()
  table.insert(signals, anchorText())
  table.insert(signals, receiptText())
  table.insert(rows, infoSection("Signals", signals))
  table.insert(rows, ui.row({ gap = 6 }, {
    hubButton("hub", "/", "Open the hub dashboard"),
    hubButton("work", "/work/", "Named workloads running right now"),
    hubButton("services", "/services/", "Runtime surfaces with lifecycle controls"),
  }))
  panel.render(ui.column({ gap = 12, padding = 16 }, rows))
end

noctalia.state.watch("sinity-hub.view", function(value)
  view = type(value) == "table" and value or { status = "disconnected" }
  render()
end)

function onOpen(_context)
  refreshWork()
  render()
end
