# NixOS Tests
#
# Additional test specifications for sinnix configuration.
# These are config assertion tests (fast, no VM boot).
#
# Note: VM tests would require refactoring how modules consume `inputs`
# (currently needed at import time, which nixosTest doesn't support well).
{ inputs, pkgs, system }:
let
  inherit (pkgs) lib;
in
{
  # No VM tests - they don't actually test sinnix modules.
  # See flake/tests.nix for the assertion tests that do test sinnix.
  all = { };
}
