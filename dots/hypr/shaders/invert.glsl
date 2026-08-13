// Photographic negative of the entire screen.
vec4 invert_shade(vec4 c, vec2 uv) {
    return vec4(1.0 - c.rgb, c.a);
}
