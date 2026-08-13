// Fold the screen into six mirrored wedges around its centre.
vec2 kaleido_warp(vec2 uv) {
    vec2 p = (uv - 0.5) * vec2(screen_size.x / screen_size.y, 1.0);
    float a = atan(p.y, p.x);
    float seg = 3.14159265 / 3.0;
    a = abs(mod(a + seg * 0.5, seg) - seg * 0.5);
    p = vec2(cos(a), sin(a)) * length(p);
    return clamp(p / vec2(screen_size.x / screen_size.y, 1.0) + 0.5, 0.0, 1.0);
}
