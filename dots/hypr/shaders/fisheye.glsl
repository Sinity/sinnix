// Bulge the middle of the screen out toward you.
vec2 fisheye_warp(vec2 uv) {
    vec2 p = uv * 2.0 - 1.0;
    float r = length(p);
    p *= mix(1.0, 0.62, exp(-r * r * 2.2));
    return p * 0.5 + 0.5;
}
