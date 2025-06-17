# Hyprland Window Manager Scripts
# Scripts for controlling Hyprland compositor features

{ pkgs, ... }:
let
  toggle_blur = pkgs.writeScriptBin "toggle_blur" ''
    #!/usr/bin/env bash
    STATE=$(${pkgs.hyprland}/bin/hyprctl getoption decoration:blur:enabled | ${pkgs.gawk}/bin/awk 'NR==1{print $2}')
    if [ "$STATE" = "1" ]; then
        ${pkgs.hyprland}/bin/hyprctl keyword decoration:blur:enabled false
    else
        ${pkgs.hyprland}/bin/hyprctl keyword decoration:blur:enabled true
    fi
  '';

  toggle_opacity = pkgs.writeScriptBin "toggle_opacity" ''
    #!/usr/bin/env bash
    STATE=$(${pkgs.hyprland}/bin/hyprctl getoption decoration:inactive_opacity | ${pkgs.gawk}/bin/awk 'NR==1{print $2}')
    if [ "$STATE" = "0.900000" ]; then
        ${pkgs.hyprland}/bin/hyprctl keyword decoration:inactive_opacity 1.0
    else
        ${pkgs.hyprland}/bin/hyprctl keyword decoration:inactive_opacity 0.9
    fi
  '';

  toggle_waybar = pkgs.writeScriptBin "toggle_waybar" ''
    #!/usr/bin/env bash
    if ${pkgs.procps}/bin/pgrep -x waybar > /dev/null; then
        ${pkgs.procps}/bin/pkill waybar
    else
        ${pkgs.waybar}/bin/waybar &
    fi
  '';

  show-keybinds = pkgs.writeScriptBin "show-keybinds" ''
    #!/usr/bin/env bash
    config_file=~/.config/hypr/hyprland.conf
    keybinds=$(${pkgs.gnugrep}/bin/grep -oP '(?<=bind=).*' $config_file)
    keybinds=$(echo "$keybinds" | ${pkgs.gnused}/bin/sed 's/,\([^,]*\)$/ = \1/' | ${pkgs.gnused}/bin/sed 's/, exec//g' | ${pkgs.gnused}/bin/sed 's/^,//g')
    ${pkgs.tofi}/bin/tofi --width=50% <<< "$keybinds"
  '';

  # Powerful shader effects controller
  hyperfx = pkgs.writeShellApplication {
    name = "hyperfx";
    runtimeInputs = [
      pkgs.hyprland
      pkgs.libnotify
      pkgs.coreutils
    ];
    text = ''
      #!/usr/bin/env bash

      SHADER_DIR="''${FLAKE:-/realm/project/sinnix}/module"

      case "$1" in
        matrix)
          hyprctl keyword decoration:screen_shader "$SHADER_DIR/shader-matrix.glsl"
          notify-send "HyperFX" "Matrix rain activated" -t 2000
          ;;
        cyberpunk)
          hyprctl keyword decoration:screen_shader "$SHADER_DIR/shader-cyberpunk.glsl"
          notify-send "HyperFX" "Cyberpunk mode activated" -t 2000
          ;;
        warp|reality)
          hyprctl keyword decoration:screen_shader "$SHADER_DIR/shader-reality-warp.glsl"
          notify-send "HyperFX" "Reality warp activated" -t 2000
          ;;
        oled)
          # Use the hyproled shader for OLED protection
          temp_shader="/dev/shm/hyproled_shader.glsl"
          cat > "$temp_shader" <<'EOF'
      precision highp float;
      varying vec2 v_texcoord;
      uniform sampler2D tex;

      void main() {
          vec4 originalColor = texture2D(tex, v_texcoord);
          vec2 fragCoord = gl_FragCoord.xy;
          bool isEvenPixel = mod(fragCoord.x + fragCoord.y, 2.0) == 0.0;
          vec4 color = isEvenPixel ? originalColor : vec4(0.0, 0.0, 0.0, 1.0);
          gl_FragColor = color;
      }
      EOF
          hyprctl keyword decoration:screen_shader "$temp_shader"
          notify-send "HyperFX" "OLED protection activated" -t 2000
          ;;
        retro)
          # CRT TV effect
          temp_shader="/dev/shm/retro_shader.glsl"
          cat > "$temp_shader" <<'EOF'
      precision highp float;
      varying vec2 v_texcoord;
      uniform sampler2D tex;
      uniform float time;

      void main() {
          vec2 uv = v_texcoord;
          
          // CRT curvature
          vec2 crtUV = uv * 2.0 - 1.0;
          float curvature = 0.1;
          crtUV += crtUV * curvature * dot(crtUV, crtUV);
          crtUV = crtUV * 0.5 + 0.5;
          
          if (crtUV.x < 0.0 || crtUV.x > 1.0 || crtUV.y < 0.0 || crtUV.y > 1.0) {
              gl_FragColor = vec4(0.0, 0.0, 0.0, 1.0);
              return;
          }
          
          vec4 color = texture2D(tex, crtUV);
          
          // Scanlines
          float scanline = sin(crtUV.y * 800.0) * 0.04;
          color.rgb -= scanline;
          
          // Phosphor RGB strips
          float strip = mod(gl_FragCoord.x, 3.0);
          if (strip < 1.0) color.gb *= 0.7;
          else if (strip < 2.0) color.rb *= 0.7;
          else color.rg *= 0.7;
          
          // Vignette
          float vignette = 1.0 - length(uv - 0.5) * 1.0;
          color.rgb *= vignette;
          
          gl_FragColor = color;
      }
      EOF
          hyprctl keyword decoration:screen_shader "$temp_shader"
          notify-send "HyperFX" "Retro CRT mode activated" -t 2000
          ;;
        off|clear|reset)
          hyprctl keyword decoration:screen_shader ""
          notify-send "HyperFX" "Shaders disabled" -t 2000
          ;;
        *)
          echo "Usage: hyperfx [matrix|cyberpunk|warp|oled|retro|off]"
          echo ""
          echo "Effects:"
          echo "  matrix     - Matrix digital rain"
          echo "  cyberpunk  - Glitch and neon effects"  
          echo "  warp       - Reality warping fractals"
          echo "  oled       - OLED burn-in protection"
          echo "  retro      - CRT TV simulation"
          echo "  off        - Disable all effects"
          ;;
      esac
    '';
  };
in
{
  config = {
    environment.systemPackages = [
      toggle_blur
      toggle_opacity
      toggle_waybar
      show-keybinds
      hyperfx
    ];
  };
}
