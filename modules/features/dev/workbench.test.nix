{
  lib,
  mkFeatureTest,
  hmFor,
  ...
}:
mkFeatureTest {
  name = "dev-workbench";
  feature = "sinnix.features.dev.workbench.enable";
  assertions =
    config:
    let
      hm = hmFor config;
      packageNames = map (pkg: lib.getName pkg) hm.home.packages;
    in
    [
      {
        assertion = builtins.elem "strace" packageNames;
        message = "Dev workbench must keep syscall tracing available";
      }
      {
        assertion = builtins.elem "py-spy" packageNames;
        message = "Dev workbench must install py-spy for Python profiling";
      }
    ];
}
