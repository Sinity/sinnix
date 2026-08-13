// Split the colour channels radially, the way cheap glass does.
vec4 chromatic_shade(vec4 c, vec2 uv) {
    vec2 d = (uv - 0.5) * 0.008;
    return vec4(texture(tex, uv + d).r, c.g, texture(tex, uv - d).b, c.a);
}
