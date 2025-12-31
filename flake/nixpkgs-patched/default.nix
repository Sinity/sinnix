{ system ? (if builtins ? currentSystem then builtins.currentSystem else "x86_64-linux"), overlays ? [], config ? {}, ... }:
let
  lock = builtins.fromJSON (builtins.readFile ../../flake.lock);
  nixpkgsNode =
    if builtins.isList lock.nodes.root.inputs.nixpkgs then
      builtins.elemAt lock.nodes.root.inputs.nixpkgs (builtins.length lock.nodes.root.inputs.nixpkgs - 1)
    else
      lock.nodes.root.inputs.nixpkgs;
  nixpkgsLocked = lock.nodes.${nixpkgsNode}.locked;
  nixpkgsUrl =
    if nixpkgsLocked.type == "github" then
      "github:${nixpkgsLocked.owner}/${nixpkgsLocked.repo}/${nixpkgsLocked.rev}?narHash=${nixpkgsLocked.narHash}"
    else
      throw "Unsupported nixpkgs lock type: ${nixpkgsLocked.type}";
  overlay = final: prev: {
    re2 = prev.re2.overrideAttrs (old: {
      postFixup = final.lib.concatStringsSep "\n" [
        (old.postFixup or "")
        ''
          if [[ -n ''${dev:-} && -f "$dev/lib/cmake/re2/re2Config.cmake" ]]; then
            sed -i 's@set_and_check(re2_INCLUDE_DIR [^)]*)@set_and_check(re2_INCLUDE_DIR include)@' \
              "$dev/lib/cmake/re2/re2Config.cmake"
          fi
        ''
      ];
    });
  };
  patchedOverlays = overlays ++ [ overlay ];
  flake = builtins.getFlake nixpkgsUrl;
in
import flake { inherit system config; overlays = patchedOverlays; }
