--!nonstrict
-- Sinnix operations panel for current state, policy, and action receipts.

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

local function agentRows()
  if type(view.snapshot) ~= "table" or type(view.snapshot.state) ~= "table" then return nil end
  local rows = view.snapshot.state.workload_rows
  if type(rows) ~= "table" then return nil end
  local agents = {}
  for _, row in ipairs(rows) do
    if type(row) == "table" and row.kind == "attested-job" then
      table.insert(agents, row)
    end
  end
  return agents
end

local function agentText()
  local agents = agentRows()
  if agents == nil then return { "Agents: unavailable" } end
  if #agents == 0 then return { "Agents: none reported" } end
  local visible = math.min(#agents, 4)
  local lines = { "Agents: " .. tostring(#agents) .. " reported, showing " .. tostring(visible) }
  for index = 1, visible do
    local row = agents[index]
    local metrics = row.metrics or {}
    local identity = metrics.identity or {}
    local delegation = metrics.delegation or {}
    local orphan = metrics.orphan or {}
    local parent = delegation.parent_job_id or delegation.coordinator_job_id or "root"
    local state = text(row.status)
    local attestation = text(orphan.attestation)
    local age = orphan.age_seconds ~= nil and (tostring(math.floor(orphan.age_seconds / 60)) .. "m") or "unavailable"
    local provider = identity.provider or "provider unavailable"
    local artifacts = metrics.completion and metrics.completion.artifacts
    local artifactText = "unavailable"
    if type(artifacts) == "table" then
      local refs = {}
      for artifactIndex = 1, math.min(#artifacts, 2) do table.insert(refs, tostring(artifacts[artifactIndex])) end
      artifactText = #refs > 0 and table.concat(refs, ", ") or "none"
      if #artifacts > #refs then artifactText = artifactText .. " (" .. tostring(#artifacts - #refs) .. " more)" end
    end
    table.insert(lines, "  " .. text(row.name) .. " under " .. tostring(parent) .. ": " .. state .. ", " .. tostring(provider) .. ", " .. attestation .. ", age " .. age .. ", artifacts " .. artifactText)
  end
  if #agents > visible then table.insert(lines, "  " .. tostring(#agents - visible) .. " more agents in the snapshot") end
  return lines
end

local function quotaText()
  local gateway = stateValue("agent_gateway")
  if type(gateway) ~= "table" or type(gateway.quota) ~= "table" then return { "Quotas: unavailable" } end
  local quota = gateway.quota
  local lines = { "Quotas: " .. text(quota.provenance) .. ", freshness " .. text(quota.freshness) }
  if type(quota.values) ~= "table" or next(quota.values) == nil then
    table.insert(lines, "  provider quota: unavailable")
    table.insert(lines, "  local tokens: unavailable")
    table.insert(lines, "  API-equivalent cost: unavailable")
    return lines
  end
  local seen = { provider = false, local_tokens = false, cost = false }
  for key, value in pairs(quota.values) do
    local item = type(value) == "table" and value or { value = value }
    local kind = item.kind or item.category or key
    local label = tostring(kind)
    if kind == "provider_quota" or kind == "provider" then seen.provider = true end
    if kind == "local_tokens" or kind == "local" then seen.local_tokens = true end
    if kind == "api_equivalent_cost" or kind == "cost" then seen.cost = true end
    local overlap = item.attribution_overlap and "; overlapping attribution" or ""
    local forecast = item.forecast and ("; forecast " .. text(item.forecast.source) .. "/" .. text(item.forecast.confidence)) or ""
    table.insert(lines, "  " .. label .. ": used " .. text(item.used) .. ", remaining " .. text(item.remaining) .. ", units " .. text(item.native_units) .. overlap .. forecast)
  end
  if not seen.provider then table.insert(lines, "  provider quota: unavailable") end
  if not seen.local_tokens then table.insert(lines, "  local tokens: unavailable") end
  if not seen.cost then table.insert(lines, "  API-equivalent cost: unavailable") end
  return lines
end

local function infoSection(title, lines)
  local children = { ui.label({ text = title, fontWeight = "bold", color = "primary" }) }
  for _, line in ipairs(lines) do
    table.insert(children, ui.label({ text = line, color = "on_surface" }))
  end
  return ui.column({ gap = 4, padding = 8, fill = "surface_variant/0.25", radius = 6 }, children)
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

local function attentionText()
  local attention = stateValue("attention")
  if type(attention) ~= "table" then return "unavailable" end
  return tostring(attention.pending_count or 0) .. " pending"
end

local function policyText()
  local inventory = stateValue("runtime_inventory")
  if type(inventory) ~= "table" or type(inventory.surfaces) ~= "table" then return "unavailable" end
  local declared = 0
  local live = 0
  for _, surface in pairs(inventory.surfaces) do
    if type(surface) == "table" then
      if type(surface.effectiveResources) == "table" then declared = declared + 1 end
      if type(surface.resources) == "table" then live = live + 1 end
    end
  end
  return tostring(declared) .. " declared, " .. tostring(live) .. " live policies"
end

local function receiptText()
  if type(view.receipts) ~= "table" or type(view.receipts.receipts) ~= "table" then return "unavailable" end
  local receipts = view.receipts.receipts
  if #receipts == 0 then return "none" end
  local latest = receipts[#receipts]
  return tostring(#receipts) .. " recent, latest " .. text(latest.action) .. " " .. text(latest.adapter and latest.adapter.status)
end

local function ambientText()
  local ambient = stateValue("ambient_intelligence")
  if type(ambient) ~= "table" then return "unavailable" end
  local fragmentation = ambient.fragmentation or {}
  local nudge = fragmentation.nudge or {}
  local anomalies = ambient.anomalies or {}
  local chores = ambient.chores or {}
  return "fragmentation " .. text(fragmentation.risk) .. ", " .. tostring(#anomalies) .. " anomalies, " .. tostring(#chores) .. " chores, nudge " .. text(nudge.reason)
end

local function anchorText()
  local anchor = stateValue("session_anchor")
  if type(anchor) ~= "table" then return "none" end
  local brief = anchor.brief or {}
  return text(brief.focused_project) .. ", " .. tostring(#(brief.recent_commits or {})) .. " commit refs, " .. tostring(#(brief.resumable_agents or {})) .. " agent refs"
end

local function render()
  local rows = {
    ui.label({ text = "Sinnix operations", fontSize = 18, fontWeight = "bold", color = "primary" }),
    ui.label({ text = "Connection: " .. text(view.status) .. "  Source: " .. text(view.source), color = view.status == "connected" and "primary" or "error" }),
    ui.label({ text = "Reason: " .. text(view.reason), color = "on_surface_variant" }),
    ui.column({ gap = 6, padding = 10, fill = "surface_variant/0.4", radius = 8 }, {
      ui.label({ text = "Pressure and memory: " .. pressureText(), color = "on_surface" }),
      ui.label({ text = "GPU: " .. compact(stateValue("gpu")), color = "on_surface" }),
      ui.label({ text = "Workload policy: " .. policyText(), color = "on_surface" }),
      ui.label({ text = "Heavy lease: " .. compact(stateValue("agent_gateway")), color = "on_surface" }),
      ui.label({ text = "Drift: " .. gapText(), color = "on_surface" }),
      ui.label({ text = "Backup and capture: " .. compact(stateValue("storage")), color = "on_surface" }),
      ui.label({ text = "Incidents: " .. incidentText(), color = "on_surface" }),
      ui.label({ text = "Attention: " .. attentionText(), color = "on_surface" }),
      ui.label({ text = "Action receipts: " .. receiptText(), color = "on_surface" }),
      ui.label({ text = "Ambient intelligence: " .. ambientText(), color = "on_surface" }),
      ui.label({ text = "AFK return: " .. anchorText(), color = "on_surface" }),
    }),
    infoSection("Agents", agentText()),
    infoSection("Quotas", quotaText()),
    ui.label({ text = "Actions use the typed reducer contract. Data expires after the configured freshness window.", color = "on_surface_variant", fontSize = 12 }),
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
