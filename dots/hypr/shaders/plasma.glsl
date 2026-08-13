// Animated. Demoscene plasma blended over the desktop.
vec4 plasma_shade(vec4 c, vec2 uv) {
    vec2 p = uv * vec2(screen_size.x / screen_size.y, 1.0) * 6.0;
    float v = sin(p.x + time) + sin(p.y + time * 1.3)
            + sin((p.x + p.y) * 0.7 + time * 0.7)
            + sin(length(p - 3.0) * 1.4 - time * 1.7);
    vec3 col = sx_hsv2rgb(vec3(fract(v * 0.125 + time * 0.02), 0.75, 1.0));
    return vec4(mix(c.rgb, col, 0.35), c.a);
}
