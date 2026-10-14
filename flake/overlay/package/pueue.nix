# Keep the host daemon and AgentCTL's client on the same ownership protocol.
# recheck: when upstream Pueue provides durable compare-and-release admission tokens.
{ ... }:
_final: prev: {
  pueue = prev.callPackage ../../../pkgs/pueue/pkg.nix { pueue = prev.pueue; };
}
