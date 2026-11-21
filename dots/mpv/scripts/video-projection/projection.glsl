//!PARAM projection
//!TYPE DYNAMIC int
0

//!PARAM layout_mode
//!TYPE DYNAMIC int
0

//!PARAM swap_eye
//!TYPE DYNAMIC int
0

//!PARAM source_fov
//!TYPE DYNAMIC float
180.0

//!PARAM view_fov
//!TYPE DYNAMIC float
90.0

//!PARAM yaw
//!TYPE DYNAMIC float
0.0

//!PARAM pitch
//!TYPE DYNAMIC float
0.0

//!HOOK MAIN
//!BIND HOOKED
//!DESC Perspective projection
//!WIDTH 1920
//!HEIGHT 1080

vec4 hook() {
    vec2 view = HOOKED_pos * 2.0 - 1.0;
    vec2 plane = view * tan(radians(view_fov * 0.5)) * vec2(1.0, 9.0 / 16.0);
    vec3 ray = normalize(vec3(plane, 1.0));
    float p = radians(pitch);
    ray.yz = mat2(cos(p), sin(p), -sin(p), cos(p)) * ray.yz;
    float y = radians(yaw);
    ray.xz = mat2(cos(y), -sin(y), sin(y), cos(y)) * ray.xz;
    vec2 eye;
    if (projection == 2) {
        float radius = acos(clamp(ray.z, -1.0, 1.0)) / radians(source_fov * 0.5);
        if (radius > 1.0)
            return vec4(0.0, 0.0, 0.0, 1.0);
        eye = vec2(0.5) + 0.5 * radius * ray.xy / max(length(ray.xy), 1e-6);
    } else {
        eye = vec2(0.5) + vec2(atan(ray.x, ray.z) / radians(source_fov), asin(clamp(ray.y, -1.0, 1.0)) / 3.14159265);
        if (source_fov >= 360.0)
            eye.x = fract(eye.x);
        else if (eye.x < 0.0 || eye.x > 1.0)
            return vec4(0.0, 0.0, 0.0, 1.0);
    }
    vec2 cells = layout_mode == 1 ? vec2(2.0, 1.0) : layout_mode == 2 ? vec2(1.0, 2.0) : vec2(1.0);
    vec2 offset = float(swap_eye) * (cells - 1.0);
    // Clamp interpolation to the chosen eye, including on the seam.
    vec2 margin = 0.5 * HOOKED_pt * cells;
    return HOOKED_tex((clamp(eye, margin, 1.0 - margin) + offset) / cells);
}
