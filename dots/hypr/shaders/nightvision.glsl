// Image-intensifier tube: green phosphor, sensor grain, blown-out highlights.
vec4 nightvision_shade(vec4 c, vec2 uv) {
    float l = pow(clamp(sx_luma(c.rgb) * 2.4, 0.0, 1.0), 0.7);
    l += (sx_hash12(uv * screen_size) - 0.5) * 0.14;
    float v = smoothstep(1.1, 0.4, length(uv - 0.5) * 1.414);
    return vec4(vec3(0.12, 1.0, 0.28) * clamp(l, 0.0, 1.0) * v, c.a);
}
