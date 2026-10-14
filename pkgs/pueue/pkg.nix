# recheck: when upstream Pueue provides durable compare-and-release admission tokens.
{ pueue }:
if pueue.sinnixPauseOwnership or false then
  pueue
else
  pueue.overrideAttrs (old: {
    patches = (old.patches or [ ]) ++ [ ../../flake/overlay/patch/pueue/owned-admission.patch ];
    # nixpkgs passes `--test client_tests` after Cargo's `--`, making it a
    # libtest name filter that selects zero tests. Run the actual suites.
    checkFlags = [
      "--skip=test_single_huge_payload"
      "--skip=test_create_unix_socket"
    ];
    passthru = (old.passthru or { }) // {
      sinnixPauseOwnership = true;
    };
  })
