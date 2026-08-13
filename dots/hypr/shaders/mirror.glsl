// Reflect the left half of the screen onto the right.
vec2 mirror_warp(vec2 uv) {
    return vec2(min(uv.x, 1.0 - uv.x), uv.y);
}
