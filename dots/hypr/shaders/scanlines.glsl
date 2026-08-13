// CRT raster lines, with a brightness lift to pay for what they eat.
vec4 scanlines_shade(vec4 c, vec2 uv) {
    float line = 0.5 + 0.5 * cos(uv.y * screen_size.y * 3.14159265);
    return vec4(clamp(c.rgb * (1.0 - 0.4 * line) * 1.3, 0.0, 1.0), c.a);
}
