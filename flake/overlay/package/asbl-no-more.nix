{ inputs }:
final: _prev:
let
  asblRuntimeInputs = with final; [
    bash
    coreutils
    procps
  ];
in
{
  asbl-no-more = final.writeShellApplication {
    name = "asbl-no-more";
    runtimeInputs = asblRuntimeInputs;
    text = ''
      exec ${final.bash}/bin/bash ${inputs.self}/scripts/asbl-no-more "$@"
    '';
  };
}
