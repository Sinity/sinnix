# Evaluates the Sinnix bridge's deployed NATS security contract without
# building a host toplevel or starting a service.
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
        name = "sinex-nats-security";
        modules = [
          mountTmpfsRoots
          baseTestConfig
          inputs.sinex.nixosModules.default
          ../../modules/services/sinex/bridge.nix
          ({ ... }: {
            networking.hostName = "sinex-nats-security";
            sinnix.services.sinex = {
              prepareHost = true;
              enable = true;
              provisionDatabase = false;
              activationProfile = "full";
            };
          })
        ];
        assertions = config: [
          {
            assertion = config.services.sinex.nats.tls.enable;
            message = "The Sinnix-managed NATS listener must enable TLS.";
          }
          {
            assertion = config.services.sinex.nats.authorization.sharedClient.enable;
            message = "The Sinnix-managed NATS listener must require shared-client authorization.";
          }
          {
            assertion = config.services.nats.settings.authorization.users != [ ];
            message = "The rendered NATS server configuration must contain an authenticated user.";
          }
          {
            assertion = config.services.sinex.runtime.nats.servers == [ "tls://127.0.0.1:4222" ];
            message = "Managed Sinex clients must use the TLS NATS endpoint.";
          }
          {
            assertion = config.services.sinex.runtime.nats.tls.requireTls;
            message = "Managed Sinex clients must reject non-TLS NATS endpoints.";
          }
          {
            assertion =
              toString config.services.sinex.runtime.nats.tls.caCertFile == "/run/agenix/sinex-nats-ca";
            message = "Managed Sinex clients must verify the NATS server with the agenix CA.";
          }
          {
            assertion =
              toString config.services.sinex.runtime.nats.auth.nkeySeedFile
              == "/run/agenix/sinex-nats-client-nkey";
            message = "Managed Sinex clients must use the agenix NKey seed.";
          }
        ];
      };
    in
    {
      checks.sinex-nats-security =
        pkgs.runCommand "sinnix-sinex-nats-security"
          {
            securityContract = builtins.toJSON {
              tls = evaluated.config.services.sinex.nats.tls.enable;
              authorization = evaluated.config.services.sinex.nats.authorization.sharedClient.enable;
              endpoint = evaluated.config.services.sinex.runtime.nats.servers;
            };
          }
          ''
            test -n "$securityContract"
            touch "$out"
          '';
    };
}
