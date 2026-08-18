"""The /shaders/ page: the Hyprland screen-shader library, and what is applied."""

from __future__ import annotations

import json
import os
import shutil
import subprocess
from pathlib import Path
from typing import Any

from .probes import load_json
from .shell import badge, card, empty, esc, kv_table, page, row, tile

SHADER_LIVE_UNIFORMS = ("time", "pointer_position", "pointer_last_active")

SHADER_CONTROL_NOTE = (
    "There are no buttons on this page. Applying a screen shader is not a verb "
    "the ops-reducer's action API has: that API admits lifecycle verbs on "
    "attested runtime-inventory units and <code>interrupt</code> on agent jobs, "
    "and a shader is neither. Giving the hub its own path to "
    "<code>hyprctl</code> would be the second control plane sinnix does "
    "not have. So the page reports, and the commands below are what drives it — "
    "from a terminal, or from <kbd>F4</kbd> / <kbd>Shift+F4</kbd> / "
    "<kbd>Super+F4</kbd> / <kbd>Super+Shift+F4</kbd>."
)


def shader_presets(manifest: dict[str, Any]) -> list[tuple[str, str]]:
    directory = manifest.get("shadersDir")
    if not directory:
        return []
    try:
        text = (Path(directory) / "_presets.conf").read_text(encoding="utf-8")
    except OSError:
        return []
    found = []
    for line in text.splitlines():
        line = line.split("#", 1)[0].strip()
        if "=" in line:
            name, _, members = line.partition("=")
            if name.strip() and members.split():
                found.append((name.strip(), " ".join(members.split())))
    return found


def shader_library(manifest: dict[str, Any]) -> list[dict[str, str]]:
    directory = manifest.get("shadersDir")
    if not directory:
        return []
    found = []
    for path in sorted(Path(directory).glob("*.glsl")):
        if path.name.startswith("_"):
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except OSError:
            continue
        lines = text.splitlines()
        description = lines[0].lstrip("/ ").strip() if lines and lines[0].startswith("//") else ""
        found.append(
            {
                "name": path.stem,
                "description": description,
                "warps": "yes" if f"{path.stem}_warp" in text else "",
                "shades": "yes" if f"{path.stem}_shade" in text else "",
                "live": ", ".join(u for u in SHADER_LIVE_UNIFORMS if u in text),
            }
        )
    return found


def hypr_option(name: str, field: str) -> Any:
    binary = shutil.which("hyprctl")
    if binary is None:
        return None
    try:
        result = subprocess.run(
            [binary, "getoption", name, "-j"], capture_output=True, text=True, timeout=10, check=False
        )
        return json.loads(result.stdout).get(field)
    except (OSError, subprocess.SubprocessError, json.JSONDecodeError, ValueError):
        return None


def render_shaders(manifest: dict[str, Any], generated: str) -> str:
    host = str(manifest.get("host", "sinnix"))
    library = shader_library(manifest)

    active = hypr_option("decoration:screen_shader", "str") or ""
    if active == "[[EMPTY]]":
        active = ""
    damage = hypr_option("debug:damage_tracking", "int")
    fp16 = hypr_option("render:use_fp16", "int")

    state, _ = load_json(
        Path(os.environ.get("XDG_RUNTIME_DIR", "/run/user/1000")) / "sinnix" / "shader" / "state.json"
    )
    applied = (state or {}).get("stages") or []

    if active and applied:
        headline = " + ".join(applied)
        tone = "info"
    elif active:
        headline = "a shader not applied through sinnix-shader"
        tone = "warn"
    else:
        headline = "none"
        tone = "ok"

    body = (
        '<div class="tiles">'
        + tile(str(len(library)), "shaders in library")
        + tile(headline, "active", tone)
        + tile(
            "on" if damage == 0 else "off",
            "animation",
            "info" if damage == 0 else "",
        )
        + tile(str(fp16) if fp16 is not None else "—", "render:use_fp16", "" if fp16 == 0 else "warn")
        + "</div>"
    )

    if hypr_option("decoration:screen_shader", "str") is None:
        body += card(
            "Hyprland not reachable",
            '<p class="sub">This renderer could not run <code>hyprctl</code>, so the '
            "state above is unknown rather than idle.</p>",
            wide=True,
        )

    rows = ""
    for entry in library:
        meta = []
        if entry["warps"] and entry["shades"]:
            meta.append("warps and shades")
        elif entry["warps"]:
            meta.append("warps the sampling coordinate")
        else:
            meta.append("shades the sampled colour")
        if entry["live"]:
            meta.append(badge("needs animation on", "warn"))
        if entry["name"] in applied and active:
            meta.append(badge("applied", "ok"))
        rows += row(
            f"<strong>{esc(entry['name'])}</strong> — {esc(entry['description'])}",
            meta,
        )

    body += card(
        "The library",
        rows or empty("no shaders found"),
        subtitle=(
            f"<code>{esc(manifest.get('shadersDir', ''))}</code>, reached through "
            "<code>~/.config/hypr/shaders</code> as an out-of-store symlink: edit a "
            "stage and re-apply, no rebuild."
        ),
        wide=True,
    )

    body += card(
        "Yes, they compose",
        "<p>Hyprland takes exactly one <code>decoration:screen_shader</code> path, "
        "so nothing stacks at the compositor — but that is not the end of the "
        "answer. <code>sinnix-shader apply a b c</code> <em>composes</em> the named "
        "stages into one generated fragment shader: every warp applied to the "
        "sampling coordinate in order, one texture fetch, then every shade in "
        "order. Any number of stages, one pass.</p>"
        "<p>Order is not decoration. <code>posterize filmgrain</code> lays grain "
        "over a flat image; <code>filmgrain posterize</code> quantises the grain "
        "away and looks like neither. Warps always land before shades regardless "
        "of where they are named, because there is only one texture fetch to place "
        "them around.</p>"
        "<p class=\"sub\">The one real limit: a stage that resamples the screen "
        "itself — <code>chromatic</code>, <code>edges</code>, <code>bloom</code>, "
        "<code>sketch</code>, <code>vhs</code> — reads the original image, not the "
        "previous stage's output, because one pass has no intermediate buffer to "
        "read back. So <code>invert edges</code> traces edges of the "
        "<em>un-inverted</em> screen and then inverts them. Stack at most one "
        "resampling stage per composition and put it last if you want it to look "
        "like what you asked for.</p>",
        wide=True,
    )

    preset_rows = shader_presets(manifest)
    if preset_rows:
        body += card(
            "Compositions worth keeping",
            kv_table([(name, f"<code>{esc(members)}</code>") for name, members in preset_rows]),
            subtitle=(
                "Named in <code>_presets.conf</code> beside the stages, so they are "
                "editable without a rebuild. Apply one by name: "
                "<code>sinnix-shader apply television</code>."
            ),
            wide=True,
        )

    body += card(
        "Playback",
        "<p><code>sinnix-shader play</code> cycles the library — or a named set of "
        "shaders and presets — on an interval. Fast intervals are their own effect: "
        "at a quarter of a second the switching itself reads as animation, on stages "
        "that hold perfectly still individually.</p>"
        "<p><code>--crossfade</code> makes the transition continuous rather than a "
        "cut. It is not a trick: both pipelines are generated into a single shader "
        "and mixed on the <code>time</code> uniform, so the fade happens per-pixel "
        "on the GPU, and it needs animation on for the same reason everything else "
        "does.</p>"
        "<p class=\"sub\">It runs as a transient systemd unit whose "
        "<code>ExecStopPost</code> clears the screen — the one teardown a signal "
        "handler cannot promise. <code>SIGKILL</code> on the loop still restores the "
        "shader, fp16 and damage tracking; verified, not assumed. Steady-state cost "
        "of switching four times a second is about 6% of one core, spent almost "
        "entirely on <code>hyprctl</code> process spawns rather than on the GPU.</p>",
        wide=True,
    )

    body += card(
        "Animation, and what it costs",
        "<p>Hyprland does expose a <code>time</code> uniform to screen shaders, "
        "and a pointer position — but it pins them to constants unless "
        "<code>debug:damage_tracking</code> is <code>0</code>, because with damage "
        "tracking on it has no reason to redraw a screen that has not changed. So "
        "animation is real, not faked, and it is bought by redrawing the whole "
        "screen every frame for as long as it is on.</p>"
        "<p>Measured on DP-3 at 3840×2160/120Hz, from Hyprland's own "
        "<code>debug:overlay</code> frame metrics: <strong>120fps and 1.05ms "
        "render</strong> with no shader, <strong>120fps and 0.96ms</strong> with a "
        "static shader, <strong>118fps and 1.12ms</strong> with an animated one and "
        "damage tracking off. The heaviest composition in the library "
        "(<code>vhs + crt + scanlines</code>, animated) came in at 118fps and "
        "1.06ms. GPU draw moved 76.7W to 77.8W. That is a real cost and a small "
        "one — a full-screen fragment pass is not what troubles a 3080.</p>"
        "<p class=\"sub\">Caveat on those numbers: the desktop was busy while they "
        "were taken, so it was already redrawing near-continuously. On a genuinely "
        "idle screen damage tracking would skip most frames, and the gap would be "
        "wider — bounded above by 120 full-screen passes a second at the times "
        "above.</p>"
        "<p class=\"sub\"><code>apply</code> turns it on by itself when a stage "
        "needs it and <code>off</code> puts it back; every apply decides the "
        "setting outright, so a static shader never inherits it. Shaders marked "
        "<em>needs animation on</em> above are frozen without it, not broken.</p>",
        wide=True,
    )

    body += card(
        "The error banner",
        "<p>A screen shader that reads <code>time</code> or a pointer uniform while "
        "damage tracking is on makes Hyprland paint a red banner across the top of "
        "the display: <em>\"Screen shader uses uniform 'time', which requires "
        "debug:damage_tracking to be switched off\"</em>. Turning damage tracking "
        "off <em>before</em> the shader is applied is what prevents it, and that is "
        "the order <code>sinnix-shader</code> uses — the banner is avoided rather "
        "than dismissed after the fact.</p>"
        "<p class=\"sub\">A stage's uniforms are only declared when it actually "
        "uses them, so the static shaders never trip the check at all. The overlay "
        "has no expiry, so <code>apply</code> clears any banner still up from "
        "earlier before it starts and <code>off</code> clears it on the way out; "
        "anything visible after an apply belongs to that apply. The manual "
        "equivalent is <code>hyprctl seterror disable</code>.</p>",
        wide=True,
    )

    body += card(
        "Driving it",
        kv_table(
            [
                ("list", "<code>sinnix-shader list</code>"),
                ("apply", "<code>sinnix-shader apply crt scanlines vignette</code>"),
                ("a preset", "<code>sinnix-shader apply television</code>"),
                ("flip through", "<code>sinnix-shader next</code> / <code>prev</code> / <code>random</code>"),
                ("playback", "<code>sinnix-shader play --interval 4 --crossfade 1</code>"),
                ("stop everything", "<code>sinnix-shader off</code>"),
                ("read the source", "<code>sinnix-shader show vhs</code>"),
                (
                    "last resort",
                    "<code>hyprctl keyword decoration:screen_shader '[[EMPTY]]'</code>",
                ),
            ]
        ),
        subtitle=SHADER_CONTROL_NOTE,
        wide=True,
    )

    return page(
        "shaders",
        host,
        [f"rendered {generated[11:19]}"],
        "/shaders/",
        body,
    )

