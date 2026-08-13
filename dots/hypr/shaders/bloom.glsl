// Bright areas bleed light into what surrounds them.
vec3 bloom_bright(vec2 uv) {
    vec3 s = texture(tex, uv).rgb;
    return s * smoothstep(0.55, 1.0, sx_luma(s));
}

vec4 bloom_shade(vec4 c, vec2 uv) {
    vec2 t = sx_texel() * 4.0;
    vec3 sum = vec3(0.0);
    sum += bloom_bright(uv + vec2(-t.x, -t.y)) + bloom_bright(uv + vec2(0.0, -t.y)) + bloom_bright(uv + vec2(t.x, -t.y));
    sum += bloom_bright(uv + vec2(-t.x, 0.0)) + bloom_bright(uv) * 2.0 + bloom_bright(uv + vec2(t.x, 0.0));
    sum += bloom_bright(uv + vec2(-t.x, t.y)) + bloom_bright(uv + vec2(0.0, t.y)) + bloom_bright(uv + vec2(t.x, t.y));
    return vec4(clamp(c.rgb + sum * 0.11, 0.0, 1.0), c.a);
}
