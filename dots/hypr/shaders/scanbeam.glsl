// Animated. A bright bar sweeping down the screen, photocopier-style.
vec4 scanbeam_shade(vec4 c, vec2 uv) {
    float beam = smoothstep(0.06, 0.0, abs(uv.y - fract(time * 0.35)));
    return vec4(clamp(c.rgb * (1.0 + beam * 1.4) + beam * 0.06, 0.0, 1.0), c.a);
}
