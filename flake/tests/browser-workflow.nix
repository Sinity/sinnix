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
            inventory = config.sinnix.runtime.inventory;
            bindings = builtins.toJSON hm.wayland.windowManager.hyprland.settings.bind;
            # The id is only known once the CRX is signed, so the policy is
            # generated with it rather than declared here; the derivation
            # below checks the pinned id against the packed archive.
            policySource =
              toString
                config.environment.etc."opt/chrome/policies/managed/sinnix-nav-capture.json".source;
          in
          [
            {
              assertion = lib.hasSuffix "/policy.json" policySource;
              message = "The navigation extension policy must come from the generated extension derivation.";
            }
            {
              assertion = builtins.hasAttr "sinnix-nav-capture" hm.systemd.user.services;
              message = "The browser provenance receiver must be supervised by the user manager.";
            }
            {
              assertion = lib.hasInfix "sinnix-cockpit:reading-stack" (
                builtins.readFile ../../dots/noctalia/config.toml
              );
              message = "The reading stack must stay visible on the Noctalia bar.";
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
      navCapturePolicy =
        evaluated.config.environment.etc."opt/chrome/policies/managed/sinnix-nav-capture.json".source;
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
      checks.browser-workflow =
        pkgs.runCommand "sinnix-browser-workflow"
          {
            inherit workflow;
            nativeBuildInputs = [
              pkgs.go-crx3
              pkgs.jq
            ];
          }
          ''
            ${pkgs.nodejs}/bin/node ${./nav-capture-extension.mjs} \
              ${../../browser-extensions/nav-capture/background.js} ${toString navigationPort}
            test -n "$workflow"

            # A policy that pins an id the signed archive does not have is the
            # silent failure this check exists to catch: Chrome just never
            # matches the forcelist entry.
            policy=${navCapturePolicy}
            generated="$(dirname "$policy")"
            packed="$(crx3 id "$generated/nav-capture.crx")"
            pinned="$(jq -r '.ExtensionSettings | keys[0]' "$policy")"
            forced="$(jq -r '.ExtensionInstallForcelist[0] | split(";")[0]' "$policy")"
            recorded="$(cat "$generated/extension-id")"
            for found in "$pinned" "$forced" "$recorded"; do
              if [ "$found" != "$packed" ]; then
                echo "extension id mismatch: packed=$packed policy=$found" >&2
                exit 1
              fi
            done
            ${pkgs.gnugrep}/bin/grep -q "appid=\"$packed\"" "$generated/updates.xml"
            touch "$out"
          '';
    };
}
