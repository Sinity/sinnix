// Pull the blue channel down and warm the rest, like a very mild night filter.
vec4 warmth_shade(vec4 c, vec2 uv) {
    return vec4(c.rgb * vec3(1.0, 0.93, 0.76), c.a);
}
