// Simulate tritanopia (no short-wavelength cones).
vec4 tritanopia_shade(vec4 c, vec2 uv) {
    return vec4(dot(c.rgb, vec3(1.255528, -0.076749, -0.178779)),
                dot(c.rgb, vec3(-0.078411, 0.930809, 0.147602)),
                dot(c.rgb, vec3(0.004733, 0.691367, 0.303900)), c.a);
}
