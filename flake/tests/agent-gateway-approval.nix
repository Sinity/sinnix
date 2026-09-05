# Provably fails when: an enabled gateway endpoint's approvedManifestHash
# differs from the tool manifest the built package emits for that principal,
# which is what the endpoint's approval gate refuses to start on.
{ inputs, ... }:
let
  inherit (inputs.nixpkgs) lib;
in
{
  perSystem =
    { system, ... }:
    let
      pkgs = inputs.nixpkgs.legacyPackages.${system};
      endpoints = lib.filterAttrs (_: endpoint: endpoint.enable) (
        inputs.self.nixosConfigurations.sinnix-prime.config.sinnix.services.agent-gateway.endpoints
      );
      expected = pkgs.writeText "agent-gateway-approvals.json" (
        builtins.toJSON (
          lib.mapAttrs (_: endpoint: {
            inherit (endpoint) principal approvedManifestHash;
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
            }
            ''
              export HOME="$TMPDIR/home"
              mkdir -p "$HOME"
              printf '{"stateDir": "%s/state"}\n' "$TMPDIR" > "$TMPDIR/config.json"
              status=0
              for name in $(jq -r 'keys[]' "$expected"); do
                principal=$(jq -r --arg n "$name" '.[$n].principal' "$expected")
                approved=$(jq -r --arg n "$name" '.[$n].approvedManifestHash' "$expected")
                live=$(sinnix-agent-gateway --config "$TMPDIR/config.json" --principal "$principal" manifest | jq -r .sha256)
                if [ "$live" != "$approved" ]; then
                  echo "endpoint $name ($principal): approvedManifestHash $approved but the package emits $live" >&2
                  status=1
                fi
              done
              [ "$status" = 0 ]
              touch "$out"
            '';
      };
    };
}
