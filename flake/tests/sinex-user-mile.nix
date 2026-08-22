# Evaluates the bounded first-user-mile runtime shape without building a host.
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
      inherit (testLib) baseTestConfig evalTestSpec mountTmpfsRoots;
      evaluated = evalTestSpec system {
        name = "sinex-user-mile";
        modules = [
          mountTmpfsRoots
          baseTestConfig
          inputs.sinex.nixosModules.default
          ../../modules/services/sinex/bridge.nix
          ({ ... }: {
            networking.hostName = "sinex-user-mile";
            sinnix.services.sinex = {
              prepareHost = true;
              enable = true;
              provisionDatabase = false;
              activationProfile = "user-mile";
            };
          })
        ];
        assertions =
          config:
          let
            sources = config.services.sinex.sources;
            sourceIds = map (binding: binding.source_id) config.sinex._sourceBindingsManifest;
          in
          [
            {
              assertion =
                sources.terminal.enable
                && !sources.filesystem.enable
                && !sources.browser.enable
                && !sources.desktop.enable
                && !sources.system.enable
                && !sources.document.enable;
              message = "The user-mile profile must enable only the terminal source domain.";
            }
            {
              assertion =
                lib.sort builtins.lessThan sourceIds == [
                  "terminal.atuin-history"
                  "terminal.monitor"
                ];
              message = "The user-mile source manifest must contain Atuin history and its required terminal lifecycle binding only.";
            }
            {
              assertion = !config.services.sinex.automata.enable && !config.services.sinex.shell.kitty.enable;
              message = "The user-mile profile must not start automata or Kitty integration.";
            }
          ];
      };
    in
    {
      checks.sinex-user-mile = pkgs.runCommand "sinnix-sinex-user-mile" { } ''
        cat > "$out" <<'EOF_CONTRACT'
        ${builtins.toJSON {
          sourceBindings = evaluated.config.sinex._sourceBindingsManifest;
          automataEnabled = evaluated.config.services.sinex.automata.enable;
          kittyEnabled = evaluated.config.services.sinex.shell.kitty.enable;
        }}
        EOF_CONTRACT
      '';
    };
}
