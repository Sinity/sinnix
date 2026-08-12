# Tailnet hub renderer: scope-command parsing and the control-surface
# admission rule it shares with the ops-reducer's action API.
{ inputs, ... }:
{
  perSystem =
    { system, ... }:
    let
      pkgs = inputs.nixpkgs.legacyPackages.${system};
    in
    {
      checks.hub-render = pkgs.runCommand "hub-render-check" { } ''
        ${pkgs.python3}/bin/python3 ${../tests/hub-render.py} \
          ${../../scripts/sinnix-hub-render}
        touch "$out"
      '';
    };
}
