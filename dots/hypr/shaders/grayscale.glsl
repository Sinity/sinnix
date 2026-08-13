// Drop all colour, keep perceptual luminance.
vec4 grayscale_shade(vec4 c, vec2 uv) {
    return vec4(vec3(sx_luma(c.rgb)), c.a);
}
