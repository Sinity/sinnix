# recheck: remove when the pinned NixOS switch applies changed socket definitions
# with active-holder conservation and real listener transition tests.
{ ... }:
_final: prev: {
  switch-to-configuration-ng = prev.switch-to-configuration-ng.overrideAttrs (old: {
    patches = (old.patches or [ ]) ++ [
      (prev.writeText "switch-to-configuration-sockets.patch" (
        builtins.readFile ./switch-to-configuration-sockets.patch
      ))
    ];
  });
}
