// Helpers available to every stage. Not a shader; never listed or applied alone.

float sx_luma(vec3 c) {
    return dot(c, vec3(0.2126, 0.7152, 0.0722));
}

vec2 sx_texel() {
    return 1.0 / max(screen_size, vec2(1.0));
}

float sx_hash12(vec2 p) {
    vec3 p3 = fract(vec3(p.xyx) * 0.1031);
    p3 += dot(p3, p3.yzx + 33.33);
    return fract((p3.x + p3.y) * p3.z);
}

vec2 sx_hash22(vec2 p) {
    vec3 p3 = fract(vec3(p.xyx) * vec3(0.1031, 0.1030, 0.0973));
    p3 += dot(p3, p3.yxz + 33.33);
    return fract((p3.xx + p3.yz) * p3.zy);
}

float sx_vnoise(vec2 p) {
    vec2 i = floor(p);
    vec2 f = fract(p);
    f = f * f * (3.0 - 2.0 * f);
    return mix(mix(sx_hash12(i), sx_hash12(i + vec2(1.0, 0.0)), f.x),
               mix(sx_hash12(i + vec2(0.0, 1.0)), sx_hash12(i + vec2(1.0, 1.0)), f.x), f.y);
}

vec3 sx_rgb2hsv(vec3 c) {
    vec4 K = vec4(0.0, -1.0 / 3.0, 2.0 / 3.0, -1.0);
    vec4 p = mix(vec4(c.bg, K.wz), vec4(c.gb, K.xy), step(c.b, c.g));
    vec4 q = mix(vec4(p.xyw, c.r), vec4(c.r, p.yzx), step(p.x, c.r));
    float d = q.x - min(q.w, q.y);
    return vec3(abs(q.z + (q.w - q.y) / (6.0 * d + 1e-10)), d / (q.x + 1e-10), q.x);
}

vec3 sx_hsv2rgb(vec3 c) {
    vec4 K = vec4(1.0, 2.0 / 3.0, 1.0 / 3.0, 3.0);
    vec3 p = abs(fract(c.xxx + K.xyz) * 6.0 - K.www);
    return c.z * mix(K.xxx, clamp(p - K.xxx, 0.0, 1.0), c.y);
}

// Recursive-halving Bayer construction: each level adds two more bits of
// threshold resolution without a lookup table. Range is [0, 0.9375).
float sx_bayer2(vec2 a) {
    a = floor(a);
    return fract(a.x * 0.5 + a.y * a.y * 0.75);
}

float sx_bayer4(vec2 a) {
    return sx_bayer2(0.5 * a) * 0.25 + sx_bayer2(a);
}

float sx_bayer8(vec2 a) {
    return sx_bayer4(0.5 * a) * 0.25 + sx_bayer2(a);
}

vec3 sx_saturate(vec3 c, float amount) {
    return clamp(mix(vec3(sx_luma(c)), c, amount), 0.0, 1.0);
}
