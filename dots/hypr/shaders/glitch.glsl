// Frozen datamosh: horizontal bands torn sideways, channels pulled apart.
vec2 glitch_warp(vec2 uv) {
    float band = floor(uv.y * 42.0);
    float tear = (sx_hash12(vec2(band, 7.0)) - 0.5) * step(0.72, sx_hash12(vec2(band, 3.0))) * 0.09;
    return vec2(fract(uv.x + tear), uv.y);
}

vec4 glitch_shade(vec4 c, vec2 uv) {
    float band = floor(uv.y * 42.0);
    float split = step(0.85, sx_hash12(vec2(band, 11.0))) * 0.012;
    return vec4(texture(tex, uv + vec2(split, 0.0)).r, c.g, texture(tex, uv - vec2(split, 0.0)).b, c.a);
}
