// Pencil study: edge energy inverted onto paper.
float sketch_l(vec2 uv, vec2 o) {
    return sx_luma(texture(tex, uv + o).rgb);
}

vec4 sketch_shade(vec4 c, vec2 uv) {
    vec2 t = sx_texel() * 1.5;
    float g = abs(sketch_l(uv, -t) - sketch_l(uv, t))
            + abs(sketch_l(uv, vec2(-t.x, t.y)) - sketch_l(uv, vec2(t.x, -t.y)));
    float ink = 1.0 - clamp(g * 4.0, 0.0, 1.0);
    float tooth = 1.0 - sx_vnoise(uv * screen_size * 0.35) * 0.10;
    return vec4(vec3(ink) * tooth * vec3(0.99, 0.97, 0.92), c.a);
}
