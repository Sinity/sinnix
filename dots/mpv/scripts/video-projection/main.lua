local mp = require "mp"
local input = require "mp.input"
local utils = require "mp.utils"

local shader = utils.join_path(mp.get_script_directory(), "projection.glsl")
local current
local views = {}
local probe
local changed_aspect
local original_aspect

local parameters = {
    projection = true,
    layout_mode = true,
    swap_eye = true,
    source_fov = true,
    view_fov = true,
    yaw = true,
    pitch = true,
}

local function restore_aspect()
    if changed_aspect then
        mp.set_property("video-aspect-override", original_aspect)
        changed_aspect = false
    end
end

local function render()
    local shaders = mp.get_property_native("glsl-shaders", {})
    local options = mp.get_property_native("glsl-shader-opts", {})
    local shader_index
    for index, path in ipairs(shaders) do
        if path == shader then
            shader_index = index
            break
        end
    end
    for name in pairs(parameters) do
        options["projection/" .. name] = nil
    end

    local view = current and current.view
    local format = current and current.format
    local enabled = view and not view.original and format
        and (format.projection == "equirect" or format.projection == "fisheye")
    if enabled then
        local settings = {
            projection = format.projection == "fisheye" and 2 or 1,
            layout_mode = ({sbs = 1, tb = 2})[format.layout] or 0,
            swap_eye = format.swap and 1 or 0,
            source_fov = format.hfov,
            view_fov = view.fov,
            yaw = view.yaw,
            pitch = view.pitch,
        }
        for name, value in pairs(settings) do
            options["projection/" .. name] = tostring(value)
        end
        if not changed_aspect then
            original_aspect = mp.get_property("video-aspect-override", "no")
            changed_aspect = true
            mp.set_property("video-aspect-override", "16:9")
        end
    else
        restore_aspect()
    end

    if shader_index and not enabled then
        table.remove(shaders, shader_index)
        mp.set_property_native("glsl-shaders", shaders)
    end
    mp.set_property_native("glsl-shader-opts", options)
    if enabled and not shader_index then
        shaders[#shaders + 1] = shader
        mp.set_property_native("glsl-shaders", shaders)
    end
end

local function clear_file()
    if probe then
        mp.abort_async_command(probe)
        probe = nil
    end
    if current then
        current = nil
        render()
    end
end

local function command(args, callback)
    return mp.command_native_async({
        name = "subprocess", args = args, playback_only = false,
        capture_stdout = true, capture_stderr = true,
    }, callback)
end

local function inspect(file, done)
    if probe then
        mp.abort_async_command(probe)
    end
    probe = command({"video-projection", "inspect", file.path}, function(ok, result)
        if current ~= file then
            if done then
                done()
            end
            return
        end
        probe = nil
        if ok and result.status == 0 then
            file.format = utils.parse_json(result.stdout)
            local rendered, failure = pcall(render)
            if not rendered then
                mp.msg.error(failure)
            end
            if file.format and file.format.kind == "vr" then
                mp.osd_message("Alt+arrows pan · Alt+PgUp/PgDn zoom · Ctrl+Alt+V settings", 4)
            end
        else
            mp.msg.warn("Could not inspect the file's projection")
        end
        if done then
            done()
        end
    end)
end

mp.register_event("start-file", clear_file)
mp.add_hook("on_preloaded", 50, function(hook)
    local path = mp.get_property("path")
    if not path or path:match("^%a[%w+.-]*://") then
        return
    end
    local has_video = false
    for _, track in ipairs(mp.get_property_native("track-list", {})) do
        if track.type == "video" and not track.image then
            has_video = true
            break
        end
    end
    if not has_video then
        return
    end
    if path:sub(1, 1) ~= "/" then
        path = utils.join_path(mp.get_property("working-directory"), path)
    end
    local info = utils.file_info(path)
    if not info or not info.is_file then
        return
    end
    local view = views[path] or {yaw = 0, pitch = 0, fov = 90, original = false}
    views[path] = view
    current = {path = path, view = view}
    hook:defer()
    inspect(current, function() hook:cont() end)
end)

local function adjust(yaw, pitch, fov)
    if not current or not current.format or current.format.kind ~= "vr" then
        return
    end
    local view = current.view
    if yaw == 0 and pitch == 0 and fov == 0 then
        view.yaw, view.pitch, view.fov = 0, 0, 90
    else
        view.yaw = (view.yaw + yaw + 180) % 360 - 180
        view.pitch = math.max(-90, math.min(90, view.pitch + pitch))
        view.fov = math.max(30, math.min(120, view.fov + fov))
    end
    render()
    mp.osd_message(string.format("Yaw %d°   Pitch %d°   View %d°", view.yaw, view.pitch, view.fov), 1)
end

local function save(file, format, layout, swap)
    if current ~= file then
        return
    end
    local args = {"video-projection", "clear", file.path}
    if format then
        args = {"video-projection", "set", file.path, "--projection", format[2],
                "--layout", layout, "--hfov", tostring(format[3])}
        if swap then
            args[#args + 1] = "--swap"
        end
    end
    command(args, function(ok, result)
        if current ~= file then
            return
        end
        if ok and result.status == 0 then
            file.view.original = false
            inspect(file)
        else
            mp.osd_message("Could not save video projection")
            mp.msg.error(result and result.stderr or "Projection helper failed")
        end
    end)
end

local formats = {
    {"Automatic", false},
    {"Flat", "flat", 180},
    {"180° equirectangular", "equirect", 180},
    {"360° equirectangular", "equirect", 360},
    {"180° fisheye", "fisheye", 180},
    {"190° fisheye", "fisheye", 190},
    {"200° fisheye", "fisheye", 200},
    {"220° fisheye", "fisheye", 220},
}

local layouts = {
    {"Mono", "mono", false},
    {"Side by side, left eye first", "sbs", false},
    {"Side by side, right eye first", "sbs", true},
    {"Top bottom, left eye first", "tb", false},
    {"Top bottom, right eye first", "tb", true},
}

local function select(prompt, choices, callback)
    local items = {}
    for index, choice in ipairs(choices) do
        items[index] = choice[1]
    end
    local selected
    input.select({
        prompt = prompt, items = items,
        submit = function(index) selected = choices[index] end,
        closed = function()
            if selected then
                -- The console unregisters the current handler after this callback.
                mp.add_timeout(0, function() callback(selected) end)
            end
        end,
    })
end

local function correct()
    local file = current
    if not file then
        return
    end
    select("Source projection", formats, function(format)
        if not format[2] then
            save(file)
        elseif format[2] == "flat" then
            save(file, format, "mono", false)
        else
            select("Stereo layout", layouts, function(layout)
                save(file, format, layout[2], layout[3])
            end)
        end
    end)
end

mp.add_key_binding("Ctrl+Alt+v", "projection-settings", correct)
mp.add_key_binding("Ctrl+Alt+o", "projection-original", function()
    if current and current.format and current.format.kind == "vr" then
        current.view.original = not current.view.original
        render()
        mp.osd_message(current.view.original and "Original video" or "Perspective view")
    end
end)

for _, binding in ipairs({
    {"Alt+LEFT", "look-left", -5, 0, 0},
    {"Alt+RIGHT", "look-right", 5, 0, 0},
    {"Alt+UP", "look-up", 0, 5, 0},
    {"Alt+DOWN", "look-down", 0, -5, 0},
    {"Alt+PGUP", "zoom-in", 0, 0, -5},
    {"Alt+PGDWN", "zoom-out", 0, 0, 5},
    {"Alt+HOME", "recenter", 0, 0, 0},
}) do
    mp.add_key_binding(binding[1], binding[2], function()
        adjust(binding[3], binding[4], binding[5])
    end, {repeatable = true})
end
