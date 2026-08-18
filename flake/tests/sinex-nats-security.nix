# Evaluates the Sinnix bridge's deployed NATS security contract without
# building a host toplevel or starting a service.
#
# The claims are made against the artifacts that actually reach the machine --
# the rendered nats-server configuration and the client runtime settings --
# rather than against the bridge's own option values, which the bridge sets
# and a test can only restate.
#
# Provably fails when: the bridge stops enabling TLS or shared-client
# authorization (the rendered server config then loses its tls block or its
# authenticated user), the listener is exposed off loopback, a client secret
# stops coming from agenix, or a client is allowed to fall back to a plaintext
# NATS endpoint.
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
        assertions =
          config:
          let
            settings = config.services.nats.settings;
            clientNats = config.services.sinex.runtime.nats;
            fromAgenix = path: lib.hasPrefix "/run/agenix/" (toString path);
          in
          [
            {
              assertion =
                (settings.tls.cert_file or null) != null
                && (settings.tls.key_file or null) != null
                && fromAgenix settings.tls.cert_file
                && fromAgenix settings.tls.key_file;
              message = "The rendered nats-server configuration must terminate TLS with agenix-provisioned key material.";
            }
            {
              assertion =
                settings.authorization.users != [ ]
                && builtins.all (
                  user: (user.nkey or null) != null && !(user ? password) && !(user ? user)
                ) settings.authorization.users;
              message = "Every rendered NATS user must authenticate by NKey, never by an embedded password.";
            }
            {
              assertion = settings.host == "127.0.0.1";
              message = "The NATS listener must stay on loopback: its authorization model assumes no off-host reachability.";
            }
            {
              assertion =
                clientNats.servers != [ ]
                && builtins.all (server: lib.hasPrefix "tls://" server) clientNats.servers
                && clientNats.tls.requireTls;
              message = "Managed Sinex clients must use TLS NATS endpoints and reject plaintext ones.";
            }
            {
              assertion = fromAgenix clientNats.tls.caCertFile && fromAgenix clientNats.auth.nkeySeedFile;
              message = "Managed Sinex clients must take their CA and NKey seed from agenix rather than the store.";
            }
          ];
      };
    in
    {
      # The claims live in the spec's assertions (forced by evalTestSpec);
      # this derivation exists to force the evaluation and to publish the
      # contract it checked.
      checks.sinex-nats-security = pkgs.runCommand "sinnix-sinex-nats-security" { } ''
        cat > "$out" <<'EOF_CONTRACT'
        ${builtins.toJSON {
          server = evaluated.config.services.nats.settings;
          client = evaluated.config.services.sinex.runtime.nats;
        }}
        EOF_CONTRACT
      '';
    };
}
