{ inputs }:
final: prev: {
  polylogue = inputs.polylogue.packages.${final.stdenv.hostPlatform.system}.default;
}
