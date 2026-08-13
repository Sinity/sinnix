// Snap sampling to a coarse grid.
vec2 pixelate_warp(vec2 uv) {
    vec2 cells = screen_size / 10.0;
    return (floor(uv * cells) + 0.5) / cells;
}
