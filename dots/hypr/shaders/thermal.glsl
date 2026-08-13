// False colour: luminance mapped onto a black-red-yellow-white heat ramp.
vec4 thermal_shade(vec4 c, vec2 uv) {
    float l = sx_luma(c.rgb);
    vec3 col = clamp(vec3(l * 3.0, l * 3.0 - 1.0, l * 3.0 - 2.0), 0.0, 1.0);
    return vec4(col, c.a);
}
