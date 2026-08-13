// Barrel-curved tube glass with an RGB aperture mask. Stack with `scanlines`.
vec2 crt_warp(vec2 uv) {
    vec2 p = uv * 2.0 - 1.0;
    p *= 1.0 + 0.10 * dot(p, p) * vec2(1.0, 1.15);
    return p * 0.5 + 0.5;
}

vec4 crt_shade(vec4 c, vec2 uv) {
    vec2 e = step(vec2(0.0), uv) * step(uv, vec2(1.0));
    float m = mod(floor(uv.x * screen_size.x), 3.0);
    vec3 mask = m < 1.0 ? vec3(1.2, 0.82, 0.82)
              : m < 2.0 ? vec3(0.82, 1.2, 0.82)
                        : vec3(0.82, 0.82, 1.2);
    return vec4(c.rgb * mask * e.x * e.y, c.a);
}
