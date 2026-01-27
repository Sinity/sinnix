{ inputs }:
final: _prev:
let
  hogkillRuntimeInputs = with final; [
    bash
    coreutils
    gum
    procps
    gawk
    gnugrep
    gnused
  ];
in
{
  hogkill = final.writeShellApplication {
    name = "hogkill";
    runtimeInputs = hogkillRuntimeInputs;
    text = ''
      exec ${final.bash}/bin/bash ${inputs.self}/scripts/hogkill "$@"
    '';
  };
}
