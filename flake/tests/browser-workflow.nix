{ inputs, ... }:
let
  inherit (inputs.nixpkgs) lib;
in
{
  perSystem =
    { system, ... }:
    let
      pkgs = inputs.nixpkgs.legacyPackages.${system};
      testLib = import ../test-lib.nix { inherit inputs lib; };
      inherit (testLib)
        baseTestConfig
        evalTestSpec
        hmFor
        mountTmpfsRoots
        ;
      spec = {
        name = "browser-workflow";
        modules = [
          mountTmpfsRoots
          baseTestConfig
          ({ ... }: {
            sinnix.machine.isDesktop = true;
          })
        ];
        assertions =
          config:
          let
            hm = hmFor config;
          in
          [
            {
              assertion = builtins.hasAttr "sinnix-nav-capture" hm.systemd.user.services;
              message = "The browser provenance receiver must be supervised by the user manager.";
            }
            {
              assertion = builtins.hasAttr "sinnix-reading-stack-widget" hm.systemd.user.services;
              message = "The visible reading stack must be started with the graphical session.";
            }
            {
              assertion = lib.hasInfix "sinnix-nav-capture-daemon" (
                toString hm.systemd.user.services.sinnix-nav-capture.Service.ExecStart
              );
              message = "The browser provenance receiver must execute the declared daemon package.";
            }
          ];
      };
      evaluated = evalTestSpec system spec;
      hm = hmFor evaluated.config;
      navSurface = evaluated.config.sinnix.runtime.surfaces.sinnix-nav-capture;
    in
    {
      checks.browser-workflow = pkgs.runCommand "sinnix-browser-workflow" { } ''
        test -n '${toString hm.systemd.user.services.sinnix-nav-capture.Service.ExecStart}'
        test '${toString (lib.elem ".local/state/sinnix" evaluated.config.sinnix.persistence.home.directories)}' = 1
        test '${toString (navSurface.captures != [ ])}' = 1
        test '${toString (lib.any (entry: lib.hasInfix "8767" (toString entry)) hm.systemd.user.services.sinnix-nav-capture.Service.Environment)}' = 1
        touch "$out"
      '';
    };
}
