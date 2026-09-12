# Evaluation checks for declarations that cross module ownership boundaries.
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
      inherit (testLib) evalTestSpec mkFeatureTest;
      syntheticCiphertext = builtins.toFile "sinnix-secret-fixture.age" "fixture";
      secretDeclarationLoader = import ../secret-declarations.nix;
      syntheticManifest = builtins.toFile "sinnix-secret-declarations.nix" ''
        { fixture.file = ${builtins.toJSON syntheticCiphertext}; }
      '';
      emptySecretDeclarations = secretDeclarationLoader { manifestPath = ""; };
      loadedSecretDeclarations = secretDeclarationLoader { manifestPath = syntheticManifest; };
      dotfileSpec = mkFeatureTest {
        name = "dotfile-renderer-metadata";
        feature = "sinnix.features.cli.polylogue.enable";
        extraModules = [
          (
            { mkServiceModule, ... }:
            {
              imports = [
                (mkServiceModule {
                  name = "dotfile-fixture";
                  description = "Dotfile renderer fixture";
                  meta.dotfiles.configFile.fixture = {
                    source = "fixture";
                    force = true;
                    onChange = "echo changed";
                    executable = true;
                  };
                })
              ];
              sinnix.services.dotfile-fixture.enable = true;
            }
          )
        ];
        assertions = config: [
          {
            assertion =
              config.home-manager.users.sinity.xdg.configFile.fixture.force
              && config.home-manager.users.sinity.xdg.configFile.fixture.onChange == "echo changed"
              && config.home-manager.users.sinity.xdg.configFile.fixture.executable;
            message = "dotfile renderer must preserve supported onChange, executable, and force metadata";
          }
        ];
      };
      secretSpec =
        (mkFeatureTest {
          name = "explicit-secret-declarations";
          feature = "sinnix.features.cli.polylogue.enable";
          assertions = config: [
            {
              assertion =
                config.age.secrets.fixture.file == syntheticCiphertext
                && config.age.secrets.fixture.path == "/run/agenix/fixture"
                && config.age.secrets.fixture.owner == config.sinnix.user.name
                && config.age.secrets.fixture.mode == "0400";
              message = "an explicit declaration must produce the conventional agenix path and default permissions";
            }
            {
              assertion =
                config.age.secrets.github-token.group == "nixbld"
                && config.age.secrets.github-token.mode == "0440"
                && lib.hasInfix "GITHUB_TOKEN" config.sinnix.secrets.exportScript;
              message = "an explicit declaration must preserve specialized permissions and exports";
            }
          ];
        })
        // {
          specialArgs.secretDeclarations = {
            fixture.file = syntheticCiphertext;
            github-token.file = syntheticCiphertext;
          };
        };
      duplicateSpec = mkFeatureTest {
        name = "duplicate-dotfile-owner";
        feature = "sinnix.features.cli.polylogue.enable";
        extraModules = [
          (
            { mkServiceModule, ... }:
            {
              imports = [
                (mkServiceModule {
                  name = "dotfile-first";
                  description = "First dotfile owner";
                  meta.dotfiles.configFile.fixture = "fixture";
                })
                (mkServiceModule {
                  name = "dotfile-second";
                  description = "Second dotfile owner";
                  meta.dotfiles.homeFile.".config//./fixture" = "fixture";
                })
              ];
              sinnix.services.dotfile-first.enable = true;
              sinnix.services.dotfile-second.enable = true;
            }
          )
        ];
        assertions = _: [ ];
      };
      unknownRendererSpec = mkFeatureTest {
        name = "unknown-dotfile-renderer-attribute";
        feature = "sinnix.features.cli.polylogue.enable";
        extraModules = [
          (
            { mkServiceModule, ... }:
            {
              imports = [
                (mkServiceModule {
                  name = "invalid-dotfile-renderer";
                  description = "Invalid dotfile renderer fixture";
                  meta.dotfiles.configFile.fixture = {
                    source = "fixture";
                    unsupported = true;
                  };
                })
              ];
              sinnix.services.invalid-dotfile-renderer.enable = true;
            }
          )
        ];
        assertions = _: [ ];
      };
      dotfiles = evalTestSpec system dotfileSpec;
      secrets = evalTestSpec system secretSpec;
      rejected =
        spec:
        !(builtins.tryEval (builtins.deepSeq (evalTestSpec system spec).config.assertions true)).success;
      duplicateRejected = rejected duplicateSpec;
      unknownRendererRejected = rejected unknownRendererSpec;
    in
    {
      checks.config-boundaries = pkgs.runCommand "sinnix-config-boundaries" { } ''
        test ${if dotfiles.config ? system then "1" else "0"} = 1
        test ${if secrets.config ? age then "1" else "0"} = 1
        test ${if duplicateRejected then "1" else "0"} = 1
        test ${if unknownRendererRejected then "1" else "0"} = 1
        test ${if emptySecretDeclarations == { } then "1" else "0"} = 1
        test ${if loadedSecretDeclarations.fixture.file == syntheticCiphertext then "1" else "0"} = 1
        touch "$out"
      '';
    };
}
