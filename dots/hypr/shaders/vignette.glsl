// Darken toward the corners.
vec4 vignette_shade(vec4 c, vec2 uv) {
    float v = smoothstep(1.15, 0.35, length(uv - 0.5) * 1.414);
    return vec4(c.rgb * mix(0.25, 1.0, v), c.a);
}
