{
  description = "Stub Sinex overlay (no-op).";

  inputs.nixpkgs.follows = "nixpkgs";

  outputs =
    { self, ... }:
    {
      overlays.default = _final: _prev: { };
    };
}
