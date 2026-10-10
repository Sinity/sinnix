{ inputs, ... }:
{
  perSystem =
    { system, ... }:
    let
      pkgs = inputs.nixpkgs.legacyPackages.${system};
      inherit (inputs.nixpkgs) lib;
      render =
        models:
        import ../../modules/features/cli/aichat.nix {
          inherit pkgs lib;
          helpers.data.localModels = {
            inherit models;
            ollamaApiBase = "http://127.0.0.1:12345";
          };
          mkFeatureModule =
            spec: _:
            spec.configFn {
              inherit pkgs;
              user = "fixture";
            };
        };
      text = models: (render models).home-manager.users.fixture.xdg.configFile."aichat/config.yaml".text;
      chat = {
        litellmName = "local-chat";
        ollamaTag = "fixture-chat:exact";
      };
      other = {
        litellmName = "local-coder";
        ollamaTag = "fixture-coder:exact";
      };
      config = text [
        other
        chat
      ];
      accepts = models: (builtins.tryEval (builtins.deepSeq (text models) true)).success;
      testLib = import ../test-lib.nix { inherit inputs lib; };
      host = testLib.evalTestSpec system (
        testLib.mkFeatureTest {
          name = "aichat-roster";
          feature = "sinnix.features.cli.aichat.enable";
          assertions = _: [ ];
        }
      );
      user = host.config.sinnix.user.name;
      hostText = host.config.home-manager.users.${user}.xdg.configFile."aichat/config.yaml".text;
    in
    {
      checks.aichat-roster =
        assert lib.hasInfix "model: ollama:fixture-chat:exact" config;
        assert lib.hasInfix "api_base: http://127.0.0.1:12345/v1" config;
        assert !accepts [ other ];
        assert
          !accepts [
            chat
            chat
          ];
        pkgs.runCommand "aichat-roster-check"
          {
            nativeBuildInputs = [
              pkgs.aichat
              pkgs.coreutils
              pkgs.gnugrep
            ];
          }
          ''
            export XDG_CONFIG_HOME="$TMPDIR/config"
            mkdir -p "$XDG_CONFIG_HOME/aichat"
            cp ${pkgs.writeText "aichat-config.yaml" hostText} "$XDG_CONFIG_HOME/aichat/config.yaml"
            aichat --info > info.txt
            grep -Fq 'huihui_ai/gemma-4-abliterated:12b' info.txt
            echo 'Roster selection, ambiguity rejection and native config parsing passed'
            touch "$out"
          '';
    };
}
