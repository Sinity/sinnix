# Model-free HTTP checks use the same renderer as the activation owner.
{ inputs, ... }:
let
  inherit (inputs.nixpkgs) lib;
in
{
  perSystem =
    { system, ... }:
    let
      pkgs = inputs.nixpkgs.legacyPackages.${system};
      render = import ../../modules/lib/ai-http-proxy.nix { inherit lib; };
      configFile = pkgs.writeText "ai-http-fixture.Caddyfile" (
        ''
          {
            admin off
            auto_https off
            persist_config off
          }

        ''
        + render {
          publicEndpoint = "127.0.0.1:24821";
          backendEndpoint = "127.0.0.1:24822";
          socketPath = "{$TEST_UPSTREAM}";
        }
        + render {
          publicEndpoint = "127.0.0.1:24823";
          backendEndpoint = "127.0.0.1:24824";
          socketPath = "{$TEST_UPSTREAM}";
          browserRequests = "native-only";
        }
      );
    in
    {
      checks.ai-http-boundary =
        pkgs.runCommand "ai-http-boundary-check"
          {
            nativeBuildInputs = [
              pkgs.caddy
              pkgs.python3
            ];
          }
          ''
            python3 ${./ai_http_boundary.py} ${configFile}
            touch "$out"
          '';
    };
}
