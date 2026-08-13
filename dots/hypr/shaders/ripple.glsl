// Animated. Concentric waves travelling out from the centre.
vec2 ripple_warp(vec2 uv) {
    vec2 p = uv - 0.5;
    float r = length(p);
    return uv + normalize(p + 1e-6) * sin(r * 48.0 - time * 3.0) * 0.006 * smoothstep(0.0, 0.15, r);
}
