#version 440

layout(location = 0) in vec2 qt_TexCoord0;
layout(location = 0) out vec4 fragColor;

layout(std140, binding = 0) uniform Projection {
    mat4 qt_Matrix;
    float qt_Opacity;
    float sourceFov;
    float viewFov;
    float yaw;
    float pitch;
    int fisheye;
    int layoutMode;
    int swapEye;
    vec2 sourcePixels;
    float viewAspect;
};

layout(binding = 1) uniform sampler2D source;

void main() {
    vec2 view = qt_TexCoord0 * 2.0 - 1.0;
    vec2 plane = view * tan(radians(viewFov * 0.5)) * vec2(1.0, viewAspect);
    vec3 ray = normalize(vec3(plane, 1.0));
    float p = radians(pitch);
    ray.yz = mat2(cos(p), sin(p), -sin(p), cos(p)) * ray.yz;
    float y = radians(yaw);
    ray.xz = mat2(cos(y), -sin(y), sin(y), cos(y)) * ray.xz;

    vec2 eye;
    if (fisheye != 0) {
        float radius = acos(clamp(ray.z, -1.0, 1.0)) / radians(sourceFov * 0.5);
        if (radius > 1.0) {
            fragColor = vec4(0.0, 0.0, 0.0, qt_Opacity);
            return;
        }
        eye = vec2(0.5) + 0.5 * radius * ray.xy / max(length(ray.xy), 1e-6);
    } else {
        eye = vec2(0.5) + vec2(atan(ray.x, ray.z) / radians(sourceFov),
                              asin(clamp(ray.y, -1.0, 1.0)) / 3.14159265);
        if (sourceFov >= 360.0) {
            eye.x = fract(eye.x);
        } else if (eye.x < 0.0 || eye.x > 1.0) {
            fragColor = vec4(0.0, 0.0, 0.0, qt_Opacity);
            return;
        }
    }

    vec2 cells = layoutMode == 1 ? vec2(2.0, 1.0)
               : layoutMode == 2 ? vec2(1.0, 2.0) : vec2(1.0);
    vec2 margin = 0.5 * cells / sourcePixels;
    vec2 offset = float(swapEye) * (cells - 1.0);
    vec2 uv = (clamp(eye, margin, 1.0 - margin) + offset) / cells;
    fragColor = texture(source, uv) * qt_Opacity;
}
