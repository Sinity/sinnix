// The DMG's four greens, dithered.
vec4 gameboy_shade(vec4 c, vec2 uv) {
    float l = sx_luma(c.rgb) + (sx_bayer4(uv * screen_size) - 0.47) * 0.22;
    vec3 col = l < 0.25 ? vec3(0.059, 0.220, 0.059)
             : l < 0.50 ? vec3(0.188, 0.384, 0.188)
             : l < 0.75 ? vec3(0.545, 0.675, 0.059)
                        : vec3(0.608, 0.737, 0.059);
    return vec4(col, c.a);
}
