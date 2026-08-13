// One bit per channel through a 4x4 ordered dither: eight colours, no more.
vec4 dither_shade(vec4 c, vec2 uv) {
    float t = sx_bayer4(uv * screen_size) * 1.0667;
    return vec4(step(vec3(t), c.rgb), c.a);
}
