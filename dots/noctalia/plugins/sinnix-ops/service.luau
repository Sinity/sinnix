--!nonstrict
-- Authenticated SSE bridge for the read-only Sinnix operations reducer.

local ENDPOINT = noctalia.getConfig("endpoint") or "http://127.0.0.1:3090"
local TOKEN_PATH = noctalia.getConfig("token_path") or "$XDG_RUNTIME_DIR/sinnix/ops.token"
local STALE_SECONDS = tonumber(noctalia.getConfig("stale_seconds")) or 30
local STREAM_PATH = ENDPOINT .. "/v1/events"
local SNAPSHOT_PATH = ENDPOINT .. "/v1/snapshot"
local RECEIPTS_PATH = ENDPOINT .. "/v1/receipts"
local stream = nil
local reconnectAt = 0
local lastReceived = 0
local lastSequence = nil

local function tokenPath()
  local runtime = noctalia.getenv("XDG_RUNTIME_DIR") or ""
  return noctalia.expandPath(TOKEN_PATH:gsub("%$XDG_RUNTIME_DIR", runtime))
end

local function publish(status, source, snapshot, reason)
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
  }
  noctalia.state.set("sinity-ops.view", value)
  noctalia.state.set("sinity-ops.status", status)
end

local function fallback(reason)
  local raw = noctalia.readFile(tokenPath():gsub("/ops.token$", "/status.json"))
  if raw ~= nil then
    local value = noctalia.json.decode(raw)
    if type(value) == "table" and value.schema == "sinnix-ops-v1" then
      lastReceived = noctalia.nowMs()
      publish("snapshot", "atomic-snapshot", value, reason)
      return
    end
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

local function requestSnapshot()
  local value = token()
  if value == nil or value == "" then
    fallback("capability token unavailable")
    return
  end
  noctalia.http({ url = SNAPSHOT_PATH, headers = { "Authorization: Bearer " .. value, "Accept: application/json" } }, function(response)
    if not response.ok or response.status ~= 200 then
      fallback("snapshot request failed")
      return
    end
    local decoded = noctalia.json.decode(response.body)
    if type(decoded) ~= "table" or decoded.schema ~= "sinnix-ops-v1" then
      fallback("newer or unsupported reducer schema")
      return
    end
    local source = decoded.sources and decoded.sources["sinnix-observe"]
    lastReceived = noctalia.nowMs()
    if type(source) == "table" and source.status == "healthy" then
      publish("connected", "sse", decoded, nil)
    else
      publish("source-stale", "sse", decoded, source and source.degradation or "reducer source unavailable")
    end
    noctalia.http({ url = RECEIPTS_PATH, headers = { "Authorization: Bearer " .. value, "Accept: " .. "application/json" } }, function(receipts)
      local current = noctalia.state.get("sinity-ops.view") or {}
      if receipts.ok and receipts.status == 200 then
        current.receipts = noctalia.json.decode(receipts.body)
        noctalia.state.set("sinity-ops.view", current)
      end
    end)
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
    local decoded = noctalia.json.decode(line:sub(7))
    if type(decoded) == "table" then
      lastSequence = decoded.sequence or lastSequence
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
