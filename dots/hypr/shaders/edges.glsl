// Sobel edge detection: neon wireframe on black.
float edges_l(vec2 uv, vec2 o) {
    return sx_luma(texture(tex, uv + o).rgb);
}

vec4 edges_shade(vec4 c, vec2 uv) {
    vec2 t = sx_texel();
    float gx = edges_l(uv, vec2(-t.x, -t.y)) + 2.0 * edges_l(uv, vec2(-t.x, 0.0)) + edges_l(uv, vec2(-t.x, t.y))
             - edges_l(uv, vec2(t.x, -t.y)) - 2.0 * edges_l(uv, vec2(t.x, 0.0)) - edges_l(uv, vec2(t.x, t.y));
    float gy = edges_l(uv, vec2(-t.x, -t.y)) + 2.0 * edges_l(uv, vec2(0.0, -t.y)) + edges_l(uv, vec2(t.x, -t.y))
             - edges_l(uv, vec2(-t.x, t.y)) - 2.0 * edges_l(uv, vec2(0.0, t.y)) - edges_l(uv, vec2(t.x, t.y));
    float g = clamp(sqrt(gx * gx + gy * gy) * 1.6, 0.0, 1.0);
    return vec4(sx_hsv2rgb(vec3(0.5 - 0.25 * g, 0.85, g)), c.a);
}
