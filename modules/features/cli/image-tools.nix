# Native CLI/GUI image post-processing — quick background removal and upscaling
# without spinning up ComfyUI. Complements the ComfyUI node ecosystem (SAM,
# advanced upscalers) for heavier work.
#
# - rembg:                 background removal
# - realesrgan-ncnn-vulkan: Vulkan upscaler (runs on the NVIDIA GPU, no CUDA)
# - upscayl:               GUI upscaler frontend
{
  mkFeatureModule,
  pkgs,
  ...
}@args:
mkFeatureModule {
  path = [
    "cli"
    "imageTools"
  ];
  description = "Native image post-processing tools (rembg, Real-ESRGAN, Upscayl)";
  configFn =
    { pkgs, ... }:
    {
      environment.systemPackages = with pkgs; [
        rembg
        realesrgan-ncnn-vulkan
        upscayl
      ];
    };
} args
