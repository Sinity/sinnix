local FALLBACK = require("video")
local M = {}

local function trim(s)
	return (s:gsub("%s+$", ""))
end

function M.percent(job)
	return ya.clamp(0, 10 + (job.skip or 0), 95)
end

function M.thumb(job)
	local output, err = Command("media-preview-cache")
		:arg({ "thumb-path", tostring(job.file.path), tostring(M.percent(job)) })
		:output()

	if not output then
		return nil, Err("Failed to start `media-preview-cache`, error: %s", err)
	elseif not output.status.success then
		return nil, Err("`media-preview-cache thumb-path` failed: %s", output.stderr)
	end

	local path = trim(output.stdout)
	if path == "" then
		return nil, Err("`media-preview-cache thumb-path` returned an empty path")
	end

	return Url(path)
end

function M:peek(job)
	local start, cache = os.clock(), self.thumb(job)
	if not cache then
		return FALLBACK:peek(job)
	end

	local ok, err = self:preload(job, cache)
	if not ok or err then
		return FALLBACK:peek(job)
	end

	ya.sleep(math.max(0, rt.preview.image_delay / 1000 + start - os.clock()))

	local _, show_err = ya.image_show(cache, job.area)
	if show_err then
		return FALLBACK:peek(job)
	end

	ya.preview_widget(job, nil)
end

function M:seek(job)
	local hovered = cx.active.current.hovered
	if hovered and hovered.url == job.file.url then
		local step = ya.clamp(-1, job.units, 1)
		ya.emit("peek", { math.max(0, cx.active.preview.skip + step), only_if = job.file.url })
	end
end

function M:preload(job, cache)
	cache = cache or self.thumb(job)
	if not cache then
		return FALLBACK:preload(job)
	end

	local cha = fs.cha(cache)
	if cha and cha.len > 0 then
		return true
	end

	local output, err = Command("media-preview-cache")
		:arg({ "ensure", tostring(job.file.path), tostring(M.percent(job)) })
		:output()

	if not output then
		return false, Err("Failed to start `media-preview-cache`, error: %s", err)
	elseif not output.status.success then
		return false, Err("`media-preview-cache ensure` failed: %s", output.stderr)
	end

	return true
end

function M:spot(job)
	return FALLBACK:spot(job)
end

return M
