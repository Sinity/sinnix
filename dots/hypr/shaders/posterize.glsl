// Quantise every channel to five levels: flat poster-print colour.
vec4 posterize_shade(vec4 c, vec2 uv) {
    const float levels = 5.0;
    return vec4(floor(c.rgb * levels + 0.5) / levels, c.a);
}
