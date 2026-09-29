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
      # The machine's own configuration, shared with every other check that
      # inspects it. A flake check evaluates purely, so the host receives no
      # private secret declarations; the endpoint table needs none.
      host = inputs.self.nixosConfigurations.sinnix-prime.config;
      endpoints = lib.filterAttrs (
        _: endpoint: endpoint.enable
      ) host.sinnix.services.agent-gateway.endpoints;
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
        agent-gateway-runtime =
          pkgs.runCommand "agent-gateway-runtime-check"
            {
              nativeBuildInputs = [ pkgs.python3 ];
              gatewayPackage = inputs.self.packages.${system}.sinnix-agent-gateway;
            }
            ''
              python ${./gateway-runtime-path.py} "$gatewayPackage/bin/sinnix-agent-gateway"
              touch "$out"
            '';

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
