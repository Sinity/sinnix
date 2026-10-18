--!nonstrict
-- Authenticated SSE bridge for the read-only Sinnix the hub server.

local ENDPOINT = noctalia.getConfig("endpoint") or "http://127.0.0.1:3090"
local TOKEN_PATH = noctalia.getConfig("token_path") or "$XDG_RUNTIME_DIR/sinnix/ops.token"
local STALE_SECONDS = tonumber(noctalia.getConfig("stale_seconds")) or 30
local STREAM_PATH = ENDPOINT .. "/v1/events"
-- Every async callback runs under Noctalia's 25 ms CPU budget, decode
-- included. Ask the hub server for just the state keys panel.luau reads instead
-- of the full snapshot (hundreds of KB of inventory and unit rows), and for
-- the few receipts the panel summarises.
local SNAPSHOT_STATE_KEYS = table.concat({
  "agentctl",
  "ambient_intelligence",
  "live_pressure",
  "runtime_inventory",
  "session_anchor",
  "systemd_units",
}, ",")
local SNAPSHOT_PATH = ENDPOINT .. "/v1/snapshot?state=" .. SNAPSHOT_STATE_KEYS
local RECEIPTS_PATH = ENDPOINT .. "/v1/receipts?limit=5"
local stream = nil
local reconnectAt = 0
local lastReceived = 0
local lastSequence = nil
local acceptedSequence = nil
local snapshotInFlight = false
local snapshotPending = false
local snapshotRequest = 0

local function tokenPath()
  local runtime = noctalia.getenv("XDG_RUNTIME_DIR") or ""
  return noctalia.expandPath(TOKEN_PATH:gsub("%$XDG_RUNTIME_DIR", runtime))
end

local function decodeJson(raw)
  local ok, value = pcall(noctalia.json.decode, raw)
  if ok then return value end
  return nil
end

local function acceptSnapshot(snapshot)
  -- Rereading the same fallback file does not renew its freshness.
  local sequence = tonumber(snapshot.sequence)
  if sequence == nil or (acceptedSequence ~= nil and sequence < acceptedSequence) then return false end
  if sequence ~= acceptedSequence then
    acceptedSequence = sequence
    lastReceived = noctalia.nowMs()
  end
  return true
end

local function publish(status, source, snapshot, reason, request)
  local now = noctalia.nowMs()
  local value = {
    status = status,
    source = source,
    schema = type(snapshot) == "table" and snapshot.schema or nil,
    snapshot = snapshot,
    reason = reason,
    received_at_ms = lastReceived,
    stale_after_ms = STALE_SECONDS * 1000,
    updated_at_ms = now,
    snapshot_request = request,
  }
  noctalia.state.set("sinity-ops.view", value)
  noctalia.state.set("sinity-ops.status", status)
end

local function fallback(reason)
  local raw = noctalia.readFile(tokenPath():gsub("/ops.token$", "/status.json"))
  if raw ~= nil then
    local value = decodeJson(raw)
    if type(value) == "table" and value.schema == "sinnix-ops-v1" and acceptSnapshot(value) then
      local status = noctalia.nowMs() - lastReceived > STALE_SECONDS * 1000 and "stale" or "snapshot"
      publish(status, "atomic-snapshot", value, reason)
      return
    end
  end
  if acceptedSequence ~= nil then
    publish("disconnected", "last-state", (noctalia.state.get("sinity-ops.view") or {}).snapshot, reason)
    return
  end
  local stats = noctalia.systemStats()
  if stats ~= nil then
    publish("aggregate", "noctalia-system-stats", { schema = "noctalia-aggregate-v1", state = { stats = stats } }, reason)
  else
    publish("disconnected", "none", nil, reason)
  end
end

local function token()
  local raw = noctalia.readFile(tokenPath())
  if raw == nil then return nil end
  return raw:gsub("%s+$", "")
end

local requestSnapshot
local function finishSnapshot()
  snapshotInFlight = false
  if snapshotPending then requestSnapshot() end
end

requestSnapshot = function()
  -- A burst leaves one follow-up rather than a queue of older responses.
  if snapshotInFlight then
    snapshotPending = true
    return
  end
  snapshotPending = false
  local value = token()
  if value == nil or value == "" then
    fallback("capability token unavailable")
    return
  end
  snapshotInFlight = true
  snapshotRequest = snapshotRequest + 1
  local request = snapshotRequest
  noctalia.http({ url = SNAPSHOT_PATH, headers = { "Authorization: Bearer " .. value, "Accept: application/json" } }, function(response)
    if not response.ok or response.status ~= 200 then
      fallback("snapshot request failed")
      finishSnapshot()
      return
    end
    local decoded = decodeJson(response.body)
    if type(decoded) ~= "table" or decoded.schema ~= "sinnix-ops-v1" then
      fallback("newer or unsupported hub server schema")
      finishSnapshot()
      return
    end
    if not acceptSnapshot(decoded) then
      finishSnapshot()
      return
    end
    local source = decoded.sources and decoded.sources["sinnix-observe"]
    if noctalia.nowMs() - lastReceived > STALE_SECONDS * 1000 then
      publish("stale", "sse", decoded, "last state expired", request)
    elseif type(source) == "table" and source.status == "healthy" then
      publish("connected", "sse", decoded, nil, request)
    else
      publish("source-stale", "sse", decoded, source and source.degradation or "hub server source unavailable", request)
    end
    noctalia.http({ url = RECEIPTS_PATH, headers = { "Authorization: Bearer " .. value, "Accept: " .. "application/json" } }, function(receipts)
      local current = noctalia.state.get("sinity-ops.view") or {}
      -- Shared state may copy tables; correlate the request, not table identity.
      if current.snapshot_request ~= request then return end
      if receipts.ok and receipts.status == 200 then
        local decodedReceipts = decodeJson(receipts.body)
        if type(decodedReceipts) == "table" then
          current.receipts = decodedReceipts
          noctalia.state.set("sinity-ops.view", current)
        end
      end
    end)
    finishSnapshot()
  end)
end

local function startStream()
  if stream ~= nil then return end
  local value = token()
  if value == nil or value == "" then
    fallback("capability token unavailable")
    reconnectAt = noctalia.nowMs() + 2000
    return
  end
  local headers = { "Authorization: Bearer " .. value, "Accept: text/event-stream", "Cache-Control: no-cache" }
  if lastSequence ~= nil then table.insert(headers, "Last-Event-ID: " .. tostring(lastSequence)) end
  stream = noctalia.httpStream({ url = STREAM_PATH, headers = headers }, function(line)
    if line:sub(1, 6) ~= "data: " then return end
    local decoded = decodeJson(line:sub(7))
    if type(decoded) == "table" then
      local sequence = tonumber(decoded.sequence)
      if sequence ~= nil then
        if lastSequence ~= nil and sequence <= lastSequence then return end
        lastSequence = sequence
      end
      requestSnapshot()
    end
  end, function(result)
    stream = nil
    reconnectAt = noctalia.nowMs() + 2000
    if not result.ok or result.status < 200 or result.status >= 300 then
      fallback("event stream unavailable")
    end
  end)
  if stream == nil then
    reconnectAt = noctalia.nowMs() + 2000
    fallback("event stream could not start")
  else
    requestSnapshot()
  end
end

noctalia.setUpdateInterval(1000)
fallback("starting")
startStream()

function update()
  local now = noctalia.nowMs()
  if lastReceived > 0 and now - lastReceived > STALE_SECONDS * 1000 then
    publish("stale", "last-state", (noctalia.state.get("sinity-ops.view") or {}).snapshot, "last state expired")
  end
  if stream == nil and now >= reconnectAt then startStream() end
end
