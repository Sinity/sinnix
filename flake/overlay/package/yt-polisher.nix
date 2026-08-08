# Re-export yt-polisher from the flake input while replacing its openai
# dependency with Sinnix's test-input-pruned package. The input has its own
# nixpkgs evaluation, so a normal root Python overlay cannot reach inside it.
{ inputs, ... }:
final: _prev:
let
  system = final.stdenv.hostPlatform.system;
  openai = final.python312Packages.openai.overrideAttrs (old: {
    # buildPythonPackage materializes nativeCheckInputs as
    # nativeInstallCheckInputs in the final derivation. Clearing
    # nativeCheckInputs alone is too late for overrideAttrs.
    nativeInstallCheckInputs = [ ];
    doCheck = false;
  });
  replaceOpenai = input: if final.lib.getName input == "openai" then openai else input;
  ytPolisher = inputs.yt-polisher.packages.${system}.default.overrideAttrs (old: {
    # buildPythonPackage derives propagatedBuildInputs from `dependencies`;
    # overriding only the derived field leaves the external package unchanged.
    dependencies = map (
      input: replaceOpenai input
    ) (old.dependencies or [ ]);
    # Also replace the already-materialized field; this is what the final
    # derivation uses when the input package was built by another nixpkgs.
    propagatedBuildInputs = map replaceOpenai (old.propagatedBuildInputs or [ ]);
  });
in
{
  yt-polisher = ytPolisher;
}
