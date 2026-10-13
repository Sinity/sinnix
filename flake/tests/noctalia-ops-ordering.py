"""Execute the shipped Luau bridge against controlled asynchronous callbacks."""

import os
import subprocess
import tempfile
from pathlib import Path

plugin = Path(os.environ["NOCTALIA_OPS_PLUGIN"])
setup = r"""
local now = 1000
local state = {}
local snapshots = {}
local receipts = {}
local streamCallback = nil
local streamClosed = nil
local fallbackSnapshot = nil
noctalia = {
  getConfig = function() return nil end,
  getenv = function() return "/neutral-runtime" end,
  expandPath = function(path) return path end,
  nowMs = function() return now end,
  readFile = function(path)
    if path:sub(-9) == "ops.token" then return "neutral-token" end
    return fallbackSnapshot
  end,
  systemStats = function() return nil end,
  setUpdateInterval = function() end,
  state = {
    set = function(key, value) state[key] = value end,
    get = function(key) return state[key] end,
  },
  json = {decode = function(value)
    if value == "invalid" then error("invalid JSON fixture") end
    if type(value) == "string" then return {sequence = tonumber(value)} end
    return value
  end},
  http = function(options, callback)
    if options.url:find("/v1/snapshot", 1, true) then
      table.insert(snapshots, callback)
    else
      table.insert(receipts, callback)
    end
  end,
  httpStream = function(options, callback, closed)
    streamCallback = callback
    streamClosed = closed
    return {}
  end,
}
local function snapshot(sequence)
  return {schema = "sinnix-ops-v1", sequence = sequence, state = {},
    sources = {["sinnix-observe"] = {status = "healthy"}}}
end
"""
checks = r"""
assert(#snapshots == 1, "startup must request one snapshot")
for index = 1, 10 do streamCallback("data: " .. tostring(index)) end
assert(#snapshots == 1, "SSE burst must coalesce while a snapshot is pending")
now = 2000
snapshots[1]({ok = true, status = 200, body = snapshot(12)})
assert(#snapshots == 2, "coalesced changes require one follow-up")
assert(state["sinity-ops.view"].snapshot.sequence == 12)
now = 3000
snapshots[2]({ok = true, status = 200, body = snapshot(11)})
assert(state["sinity-ops.view"].snapshot.sequence == 12, "older snapshot regressed state")
assert(state["sinity-ops.view"].received_at_ms == 2000, "older response renewed freshness")
streamCallback("data: 13")
snapshots[3]({ok = true, status = 200, body = snapshot(13)})
receipts[1]({ok = true, status = 200, body = {marker = "old"}})
assert(state["sinity-ops.view"].receipts == nil, "old receipts attached to a new snapshot")
receipts[2]({ok = true, status = 200, body = {marker = "new"}})
assert(state["sinity-ops.view"].receipts.marker == "new")
fallbackSnapshot = snapshot(11)
streamClosed({ok = false, status = 503})
assert(state["sinity-ops.view"].snapshot.sequence == 13, "fallback regressed state")
now = 40000
fallbackSnapshot = snapshot(13)
update()
snapshots[4]({ok = false, status = 503})
assert(state["sinity-ops.view"].received_at_ms == 3000, "unchanged fallback renewed freshness")
assert(state["sinity-ops.view"].status == "stale", "unchanged fallback hid expiration")
streamCallback("data: 14")
streamCallback("data: 15")
snapshots[5]({ok = false, status = 503})
assert(#snapshots == 6, "failure stranded the coalesced follow-up")
snapshots[6]({ok = true, status = 200, body = snapshot(16)})
assert(state["sinity-ops.view"].snapshot.sequence == 16)
streamCallback("data: 17")
snapshots[7]({ok = true, status = 200, body = "invalid"})
streamCallback("data: 18")
snapshots[8]({ok = true, status = 200, body = snapshot(18)})
assert(state["sinity-ops.view"].snapshot.sequence == 18, "decode failure stranded requests")
print("Noctalia bridge coalescing, ordering and receipt correlation passed")
"""
with tempfile.TemporaryDirectory(prefix="noctalia-ordering-") as directory:
    path = Path(directory) / "bridge.luau"
    path.write_text(setup + plugin.joinpath("service.luau").read_text() + checks)
    subprocess.run(["luau", str(path)], check=True)
