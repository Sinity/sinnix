#!/usr/bin/env bash
set -euo pipefail

# Practical screenshot workflow for Hyprland HDR setups.
# Captures raw screenshot(s) and can produce an optional corrected variant.

usage() {
  cat <<'USAGE'
Usage: screenshot-color-lab.sh <command> [options]

Commands:
  probe
      Show current monitor color-management status and tool availability.

  capture-output [--out-dir DIR] [--name NAME] [--fix-hdr] [--brightness PCT] [--saturation PCT] [--gamma VALUE]
      Capture focused output using both grimblast and grim.
      If --fix-hdr and current preset is hdr, create corrected variants via ImageMagick.

  capture-area [--out-dir DIR] [--name NAME] [--fix-hdr] [--brightness PCT] [--saturation PCT] [--gamma VALUE]
      Capture area (grimblast freeze picker + slurp/grim fallback).

  tone-map --in FILE [--out FILE] [--brightness PCT] [--saturation PCT] [--gamma VALUE]
      Apply manual correction transform for washed-out captures.

Defaults:
  out-dir: /realm/data/captures/screenshot
  brightness: 105
  saturation: 125
  gamma: 0.90
USAGE
}

need_cmd() {
  command -v "$1" >/dev/null 2>&1 || {
    echo "missing dependency: $1" >&2
    exit 1
  }
}

now_stamp() { date +"%Y-%m-%d-At-%Ih%Mm%Ss"; }

focused_monitor_name() {
  hyprctl -j monitors | jq -r 'map(select(.focused == true)) | .[0].name // empty'
}

focused_cm_preset() {
  hyprctl -j monitors | jq -r 'map(select(.focused == true)) | .[0].colorManagementPreset // empty'
}

apply_fix() {
  local in_file="$1" out_file="$2" brightness="$3" saturation="$4" gamma="$5"
  need_cmd magick
  magick "$in_file" -modulate "${brightness},${saturation},100" -gamma "$gamma" "$out_file"
}

cmd="${1:-}"
shift || true

case "$cmd" in
  probe)
    need_cmd hyprctl
    need_cmd jq
    have_grimblast=$(command -v grimblast >/dev/null 2>&1 && echo true || echo false)
    have_grim=$(command -v grim >/dev/null 2>&1 && echo true || echo false)
    have_slurp=$(command -v slurp >/dev/null 2>&1 && echo true || echo false)
    have_magick=$(command -v magick >/dev/null 2>&1 && echo true || echo false)
    jq -n \
      --argjson monitors "$(hyprctl -j monitors)" \
      --argjson grimblast "$have_grimblast" \
      --argjson grim "$have_grim" \
      --argjson slurp "$have_slurp" \
      --argjson magick "$have_magick" \
      '{
        focused_monitor: (($monitors | map(select(.focused == true)) | .[0]) | {
          name, currentFormat, colorManagementPreset, sdrBrightness, sdrSaturation, refreshRate
        }),
        hdr_active: (($monitors | map(select(.focused == true)) | .[0].colorManagementPreset) == "hdr"),
        tools: {grimblast: $grimblast, grim: $grim, slurp: $slurp, magick: $magick},
        note: "If hdr_active=true and screenshots look washed out, use --fix-hdr for sidecar corrected files."
      }'
    ;;

  capture-output|capture-area)
    need_cmd hyprctl
    need_cmd jq
    out_dir="/realm/data/captures/screenshot"
    name="$(now_stamp)"
    fix_hdr=0
    brightness=105
    saturation=125
    gamma=0.90

    while [[ $# -gt 0 ]]; do
      case "$1" in
        --out-dir) out_dir="${2:?missing out-dir}"; shift 2 ;;
        --name) name="${2:?missing name}"; shift 2 ;;
        --fix-hdr) fix_hdr=1; shift ;;
        --brightness) brightness="${2:?missing brightness}"; shift 2 ;;
        --saturation) saturation="${2:?missing saturation}"; shift 2 ;;
        --gamma) gamma="${2:?missing gamma}"; shift 2 ;;
        *) echo "unknown arg: $1" >&2; exit 2 ;;
      esac
    done

    mkdir -p "$out_dir"
    raw1="$out_dir/${name}.grimblast.png"
    raw2="$out_dir/${name}.grim.png"

    if [[ "$cmd" == "capture-output" ]]; then
      monitor="$(focused_monitor_name)"
      [[ -n "$monitor" ]] || { echo "could not resolve focused monitor" >&2; exit 1; }

      if command -v grimblast >/dev/null 2>&1; then
        grimblast copysave output "$raw1" >/dev/null 2>&1
      else
        echo "grimblast unavailable; skipping grimblast capture" >&2
      fi

      if command -v grim >/dev/null 2>&1; then
        grim -o "$monitor" "$raw2" >/dev/null 2>&1
      else
        echo "grim unavailable; skipping grim capture" >&2
      fi

    else
      if command -v grimblast >/dev/null 2>&1; then
        grimblast --freeze copysave area "$raw1" >/dev/null 2>&1
      else
        echo "grimblast unavailable; skipping grimblast area capture" >&2
      fi

      if command -v grim >/dev/null 2>&1 && command -v slurp >/dev/null 2>&1; then
        geom="$(slurp)"
        grim -g "$geom" "$raw2" >/dev/null 2>&1
      else
        echo "grim/slurp unavailable; skipping grim area capture" >&2
      fi
    fi

    cm="$(focused_cm_preset)"
    corrected=()
    if [[ "$fix_hdr" -eq 1 && "$cm" == "hdr" ]]; then
      for f in "$raw1" "$raw2"; do
        [[ -f "$f" ]] || continue
        out="${f%.png}.sdrfix.png"
        apply_fix "$f" "$out" "$brightness" "$saturation" "$gamma"
        corrected+=("$out")
      done
    fi

    jq -n \
      --arg cmd "$cmd" \
      --arg out_dir "$out_dir" \
      --arg cm "$cm" \
      --arg raw1 "$raw1" \
      --arg raw2 "$raw2" \
      --argjson corrected "$(printf '%s\n' "${corrected[@]:-}" | jq -R . | jq -s .)" \
      '{
        mode: $cmd,
        output_dir: $out_dir,
        color_management_preset: $cm,
        raw_files: [$raw1, $raw2] | map(select(length > 0)),
        corrected_files: $corrected
      }'
    ;;

  tone-map)
    in_file=""
    out_file=""
    brightness=105
    saturation=125
    gamma=0.90

    while [[ $# -gt 0 ]]; do
      case "$1" in
        --in) in_file="${2:?missing input}"; shift 2 ;;
        --out) out_file="${2:?missing out}"; shift 2 ;;
        --brightness) brightness="${2:?missing brightness}"; shift 2 ;;
        --saturation) saturation="${2:?missing saturation}"; shift 2 ;;
        --gamma) gamma="${2:?missing gamma}"; shift 2 ;;
        *) echo "unknown arg: $1" >&2; exit 2 ;;
      esac
    done

    [[ -n "$in_file" ]] || { echo "tone-map requires --in" >&2; exit 2; }
    [[ -f "$in_file" ]] || { echo "input file not found: $in_file" >&2; exit 1; }

    if [[ -z "$out_file" ]]; then
      out_file="${in_file%.png}.sdrfix.png"
    fi
    apply_fix "$in_file" "$out_file" "$brightness" "$saturation" "$gamma"
    jq -n --arg in "$in_file" --arg out "$out_file" '{input: $in, output: $out, status: "ok"}'
    ;;

  -h|--help|help|"")
    usage
    ;;

  *)
    echo "unknown command: $cmd" >&2
    usage >&2
    exit 2
    ;;
esac
