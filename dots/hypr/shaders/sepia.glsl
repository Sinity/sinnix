// Warm monochrome, old-photograph tone.
vec4 sepia_shade(vec4 c, vec2 uv) {
    float l = sx_luma(c.rgb);
    return vec4(clamp(l * vec3(1.07, 0.87, 0.66), 0.0, 1.0), c.a);
}
