# The package's generated principal manifest must match its running tool schemas.
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
      libContext = import ../lib-context.nix { inherit inputs; };
      # Read endpoint approval data from the host declaration under the public
      # test fixture, rather than evaluating the production host output. The
      # production output has an explicitly private secret-declaration input;
      # this approval contract does not need ciphertext to evaluate its source.
      evaluated = libContext.extendedLib.nixosSystem {
        inherit system;
        modules = testLib.baseModules ++ [
          testLib.baseTestConfig
          ../../hosts/sinnix-prime/default.nix
        ];
        specialArgs = testLib.sharedSpecialArgs // {
          lib = libContext.extendedLib;
        };
      };
      endpoints = lib.filterAttrs (_: endpoint: endpoint.enable) (
        evaluated.config.sinnix.services.agent-gateway.endpoints
      );
      expected = pkgs.writeText "agent-gateway-approvals.json" (
        builtins.toJSON (
          lib.mapAttrs (_: endpoint: {
            inherit (endpoint) principal;
          }) endpoints
        )
      );
    in
    {
      checks = lib.optionalAttrs (system == "x86_64-linux") {
        agent-gateway-approval =
          pkgs.runCommand "agent-gateway-approval-check"
            {
              nativeBuildInputs = [
                inputs.self.packages.${system}.sinnix-agent-gateway
                pkgs.jq
              ];
              inherit expected;
              gatewayPackage = inputs.self.packages.${system}.sinnix-agent-gateway;
            }
            ''
              export HOME="$TMPDIR/home"
              mkdir -p "$HOME"
              printf '{"stateDir": "%s/state"}\n' "$TMPDIR" > "$TMPDIR/config.json"
              for name in $(jq -r 'keys[]' "$expected"); do
                principal=$(jq -r --arg n "$name" '.[$n].principal' "$expected")
                manifest="$gatewayPackage/share/sinnix-agent-gateway/manifests/$principal.json"
                jq -n --arg state "$TMPDIR/state" --arg principal "$principal" --arg manifest "$manifest" \
                  '{stateDir:$state,approvedManifestPrincipal:$principal,packageManifestPath:$manifest}' > "$TMPDIR/config.json"
                sinnix-agent-gateway --config "$TMPDIR/config.json" --principal "$principal" approval-check
              done
              touch "$out"
            '';
      };
    };
}
