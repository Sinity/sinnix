// Animated. Moving film grain and a faint gate flicker.
vec4 filmgrain_shade(vec4 c, vec2 uv) {
    float g = sx_hash12(uv * screen_size + fract(time) * 733.0) - 0.5;
    float flicker = 1.0 + sin(time * 21.0) * 0.012;
    return vec4(clamp(c.rgb * flicker + g * 0.08, 0.0, 1.0), c.a);
}
