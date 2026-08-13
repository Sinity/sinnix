// Animated. Rotate every hue on the screen through the wheel.
vec4 huecycle_shade(vec4 c, vec2 uv) {
    vec3 hsv = sx_rgb2hsv(c.rgb);
    hsv.x = fract(hsv.x + time * 0.08);
    return vec4(sx_hsv2rgb(hsv), c.a);
}
