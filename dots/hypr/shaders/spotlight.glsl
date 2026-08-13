// Follows the pointer. Everything outside the torch beam falls dark.
vec4 spotlight_shade(vec4 c, vec2 uv) {
    vec2 d = (uv - pointer_position) * vec2(screen_size.x / screen_size.y, 1.0);
    float beam = smoothstep(0.22, 0.05, length(d));
    return vec4(c.rgb * mix(0.10, 1.15, beam), c.a);
}
