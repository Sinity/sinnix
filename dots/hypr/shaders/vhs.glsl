// Animated. Tape wobble, chroma bleed and head-switching noise at the bottom.
vec2 vhs_warp(vec2 uv) {
    float jitter = (sx_vnoise(vec2(uv.y * 120.0, time * 14.0)) - 0.5) * 0.004;
    float sway = sin(uv.y * 3.0 + time * 0.9) * 0.0015;
    return uv + vec2(jitter + sway, 0.0);
}

vec4 vhs_shade(vec4 c, vec2 uv) {
    vec3 col = vec3(texture(tex, uv + vec2(0.0035, 0.0)).r, c.g, texture(tex, uv - vec2(0.0035, 0.0)).b);
    col = sx_saturate(col, 0.8);
    col *= 1.0 - 0.25 * (0.5 + 0.5 * cos(uv.y * screen_size.y * 3.14159265));
    float head = smoothstep(0.055, 0.0, uv.y) * step(0.5, sx_vnoise(vec2(uv.x * 40.0, time * 9.0)));
    col = mix(col, vec3(sx_hash12(uv * screen_size + time * 91.0)), head * 0.85);
    return vec4(clamp(col, 0.0, 1.0), c.a);
}
