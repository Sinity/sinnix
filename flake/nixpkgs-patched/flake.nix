{
  description = "Nixpkgs wrapper with re2 config fix";

  inputs.nixpkgs.url = "github:NixOS/nixpkgs/nixos-unstable";

  outputs = { self, nixpkgs }:
    let
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
      forAllSystems = nixpkgs.lib.genAttrs nixpkgs.lib.systems.flakeExposed;
      mkPkgs = system: import nixpkgs { inherit system; overlays = [ overlay ]; };
    in
    {
      overlays.default = overlay;
      lib = nixpkgs.lib;
      legacyPackages = forAllSystems mkPkgs;
      packages = self.legacyPackages;
    };
}
