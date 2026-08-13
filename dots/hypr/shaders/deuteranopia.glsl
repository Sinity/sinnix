// Simulate deuteranopia (no medium-wavelength cones).
vec4 deuteranopia_shade(vec4 c, vec2 uv) {
    return vec4(dot(c.rgb, vec3(0.367322, 0.860646, -0.227968)),
                dot(c.rgb, vec3(0.280085, 0.672501, 0.047413)),
                dot(c.rgb, vec3(-0.011820, 0.042940, 0.968881)), c.a);
}
