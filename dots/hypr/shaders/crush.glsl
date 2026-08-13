// Three-bit colour with the saturation pushed up: cheap-capture-card look.
vec4 crush_shade(vec4 c, vec2 uv) {
    vec3 q = floor(sx_saturate(c.rgb, 1.6) * 8.0) / 8.0;
    return vec4(q, c.a);
}
