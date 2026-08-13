// Animated. Slow brightness swell, roughly one cycle every eight seconds.
vec4 breathe_shade(vec4 c, vec2 uv) {
    return vec4(clamp(c.rgb * (0.88 + 0.14 * sin(time * 0.785)), 0.0, 1.0), c.a);
}
