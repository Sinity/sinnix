{ inputs }:
final: prev: {
  polylogue = inputs.polylogue.packages.${final.system}.default;
}
