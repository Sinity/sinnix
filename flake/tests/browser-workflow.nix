{ inputs, ... }:
let
  inherit (inputs.nixpkgs) lib;
  navigationPort = (import ../data/ports.nix).browserNavigation;
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
            policy = builtins.fromJSON (
              builtins.unsafeDiscardStringContext
                config.environment.etc."opt/chrome/policies/managed/extra.json".text
            );
            inventory = config.sinnix.runtime.inventory;
            bindings = builtins.toJSON hm.wayland.windowManager.hyprland.settings.bind;
            extensionId = "jccgkpdlopfflfchemmfedfokldkeeck";
          in
          [
            {
              assertion =
                policy.ExtensionSettings.${extensionId}.installation_mode == "force_installed"
                && policy.ExtensionSettings.${extensionId}.override_update_url
                && lib.hasPrefix "${extensionId};file:///nix/store/" (
                  builtins.head policy.ExtensionInstallForcelist
                );
              message = "The navigation extension must be installed by Chrome's managed extension policy.";
            }
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
            {
              assertion = lib.hasInfix "SUPER + O" bindings && lib.hasInfix "sinnix-picker" bindings;
              message = "SUPER+O must reach the unified picker that consumes reading-stack entries.";
            }
            {
              assertion = lib.elem ".local/state/sinnix" config.sinnix.persistence.home.directories;
              message = "Reading-stack working state must outlive the impermanent home.";
            }
            {
              assertion = lib.any (
                entry: lib.hasInfix "SINNIX_NAV_CAPTURE_PORT=${toString navigationPort}" (toString entry)
              ) hm.systemd.user.services.sinnix-nav-capture.Service.Environment;
              message = "The provenance receiver must bind the port declared in the ports registry.";
            }
            {
              assertion =
                builtins.hasAttr "sinnix-nav-capture" inventory.surfaces
                && builtins.hasAttr "sinnix-reading-stack-widget" inventory.surfaces
                && builtins.any (capture: capture.name == "browser-nav-edges") inventory.captures
                && builtins.any (capture: capture.name == "reading-stack") inventory.captures;
              message = "The runtime inventory must declare the browser services and their capture lanes.";
            }
          ];
      };
      evaluated = evalTestSpec system spec;
      # Force the evaluated module outputs in the check derivation. Keeping
      # this read in the derivation prevents a lazy check from passing when
      # the browser module stops contributing its policy or inventory.
      workflow = builtins.unsafeDiscardStringContext (
        builtins.toJSON {
          policy = evaluated.config.environment.etc."opt/chrome/policies/managed/extra.json".text;
          inventory = evaluated.config.sinnix.runtime.inventory;
          services =
            builtins.attrNames
              evaluated.config.home-manager.users.${evaluated.config.sinnix.user.name}.systemd.user.services;
        }
      );
    in
    {
      checks.browser-workflow = pkgs.runCommand "sinnix-browser-workflow" { inherit workflow; } ''
        ${pkgs.nodejs}/bin/node ${./nav-capture-extension.mjs} \
          ${../../browser-extensions/nav-capture/background.js} ${toString navigationPort}
        test -n "$workflow"
        touch "$out"
      '';
    };
}
