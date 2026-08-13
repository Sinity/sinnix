// Simulate protanopia (no long-wavelength cones).
vec4 protanopia_shade(vec4 c, vec2 uv) {
    return vec4(dot(c.rgb, vec3(0.152286, 1.052583, -0.204868)),
                dot(c.rgb, vec3(0.114503, 0.786281, 0.099216)),
                dot(c.rgb, vec3(-0.003882, -0.048116, 1.051998)), c.a);
}
