// Animated. Slow underwater drift.
vec2 wobble_warp(vec2 uv) {
    return uv + vec2(sin(uv.y * 9.0 + time * 1.3), cos(uv.x * 11.0 + time * 1.1)) * 0.004;
}
