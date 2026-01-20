#!/usr/bin/env bash
# ASBL Reset Tester
# Tests different approaches to see what resets the FO48U's static detection
# Run this, then watch if the display dims after 5 minutes

set -euo pipefail

MODE="${1:-help}"

case "$MODE" in
    gamma-pulse)
        # Brief gamma shift via screen shader
        echo "Testing gamma pulse..."
        cat > /tmp/gamma-pulse.glsl << 'EOF'
#version 300 es
precision highp float;
in vec2 v_texcoord;
uniform sampler2D tex;
uniform float time;
out vec4 fragColor;

void main() {
    vec4 color = texture(tex, v_texcoord);
    // Pulse gamma every ~2 seconds, subtle shift
    float pulse = 1.0 + 0.03 * sin(time * 3.14159);
    fragColor = vec4(pow(color.rgb, vec3(1.0/pulse)), color.a);
}
EOF
        hyprctl keyword decoration:screen_shader /tmp/gamma-pulse.glsl
        echo "Gamma pulse shader active. Run '$0 off' to disable."
        ;;

    brightness-flash)
        # Quick brightness flash via shader
        echo "Flashing brightness..."
        cat > /tmp/bright-flash.glsl << 'EOF'
#version 300 es
precision highp float;
in vec2 v_texcoord;
uniform sampler2D tex;
out vec4 fragColor;

void main() {
    vec4 color = texture(tex, v_texcoord);
    fragColor = vec4(color.rgb * 1.1, color.a);
}
EOF
        hyprctl keyword decoration:screen_shader /tmp/bright-flash.glsl
        sleep 0.3
        hyprctl keyword decoration:screen_shader ""
        echo "Flash complete"
        ;;

    notification)
        # Hyprland notification overlay
        echo "Sending notification..."
        # White notification, 300ms, nearly transparent
        hyprctl notify 1 300 "rgba(255,255,255,0.05)" " "
        echo "Notification sent"
        ;;

    dim-toggle)
        # Toggle dim_strength
        echo "Toggling dim_strength..."
        hyprctl keyword decoration:dim_strength 0.4
        sleep 0.2
        hyprctl keyword decoration:dim_strength 0.3
        echo "Dim toggle complete"
        ;;

    invert-flash)
        # Brief color inversion (dramatic APL change)
        echo "Inverting colors briefly..."
        cat > /tmp/invert.glsl << 'EOF'
#version 300 es
precision highp float;
in vec2 v_texcoord;
uniform sampler2D tex;
out vec4 fragColor;

void main() {
    vec4 color = texture(tex, v_texcoord);
    fragColor = vec4(1.0 - color.rgb, color.a);
}
EOF
        hyprctl keyword decoration:screen_shader /tmp/invert.glsl
        sleep 0.1
        hyprctl keyword decoration:screen_shader ""
        echo "Invert flash complete"
        ;;

    off)
        echo "Disabling shader..."
        hyprctl keyword decoration:screen_shader ""
        echo "Shader disabled"
        ;;

    status)
        echo "Current shader:"
        hyprctl getoption decoration:screen_shader
        ;;

    help|*)
        cat << 'EOF'
ASBL Reset Tester - Test what resets the FO48U's static detection

Usage: test-asbl-reset.sh <mode>

Modes:
    gamma-pulse      - Continuous subtle gamma oscillation (shader)
    brightness-flash - Single brief brightness increase
    notification     - Hyprland notification overlay
    dim-toggle       - Toggle decoration dim_strength
    invert-flash     - Brief color inversion (most dramatic)
    off              - Disable any active shader
    status           - Show current shader state

Testing procedure:
1. Start with static content (terminal with text)
2. Wait ~4 minutes (before dimming typically starts)
3. Run one of the modes
4. See if display brightens back / timer resets
5. Repeat with different modes to find what works

EOF
        ;;
esac
