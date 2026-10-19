# The package's generated tool manifest must match its running tool schemas.
{ inputs, ... }:
let
  inherit (inputs.nixpkgs) lib;
in
{
  perSystem =
    { system, ... }:
    let
      pkgs = inputs.nixpkgs.legacyPackages.${system};
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

        agent-gateway-manifest =
          pkgs.runCommand "agent-gateway-manifest-check"
            {
              nativeBuildInputs = [
                inputs.self.packages.${system}.sinnix-agent-gateway
                pkgs.jq
              ];
              gatewayPackage = inputs.self.packages.${system}.sinnix-agent-gateway;
            }
            ''
              export HOME="$TMPDIR/home"
              mkdir -p "$HOME"
              jq -n --arg state "$TMPDIR/state" --arg manifest "$gatewayPackage/share/sinnix-agent-gateway/manifest.json" \
                '{stateDir:$state,packageManifestPath:$manifest}' > "$TMPDIR/config.json"
              sinnix-agent-gateway --config "$TMPDIR/config.json" manifest-check
              touch "$out"
            '';
      };
    };
}
