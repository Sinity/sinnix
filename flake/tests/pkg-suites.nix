# Packaged pytest suites (pkgs/*/pkg.nix with a checkPhase) that were never
# forced to build by any check target -- exactly the sinnix-2e46 pattern
# found in machine-telemetry/sinnix-config-drift (script-suites.nix): the
# suite existed and even worked, but no tier's dependency graph ever
# required the derivation to be realized, so a broken checkPhase left `check`
# green. Unlike script-suites.nix's subjects, these already have a real
# derivation with nativeCheckInputs/checkPhase (mirrors ops-reducer.nix and
# quota.nix, which already did this for sinnix-ops-reducer/sinnix-quota) --
# so the fix is just forcing the package to build here, not reimplementing a
# fixture around the bare script.
{ inputs, ... }:
{
  perSystem =
    { system, ... }:
    let
      pkgs = inputs.nixpkgs.legacyPackages.${system};
      scriptRegistry = import ../scripts.nix { inherit inputs pkgs; };

      # sinnix-phone-dispatcher's checkPhase needs the package built at all,
      # and its pkg.nix pulls in sinnix-steer (runtimeInputs pkgs.claude-code)
      # as steerPackage -- claude-code is unfree, and plain legacyPackages
      # (unconfigured, same instance every other check here uses) refuses to
      # even evaluate its drvPath. One locally-configured instance, same
      # pattern as flake/overlay/package/local-ai.nix's aiPkgs, rather than
      # flipping allowUnfree for every check in the tree.
      unfreePkgs = import inputs.nixpkgs {
        inherit system;
        config.allowUnfree = true;
      };
      scriptRegistryUnfree = import ../scripts.nix {
        inherit inputs;
        pkgs = unfreePkgs;
      };
    in
    {
      checks = {
        # Provably fails when: is_near_duplicate's threshold boundary stops
        # being inclusive. Verified by flipping `<= threshold` to `< threshold`
        # in hashing.py -- caught by
        # test_is_near_duplicate_threshold_is_inclusive_boundary (1 failed,
        # 53 passed); reverted after confirming red.
        sinnix-capture-screen-suite = scriptRegistry.packageSet.sinnix-capture-screen;

        # Provably fails when: the "5m"/"2h" duration-unit table drifts from
        # real seconds. Verified by changing the minute multiplier 60.0 ->
        # 61.0 in pause.py -- caught by test_parse_duration[5m-300.0] (1
        # failed, 60 passed); reverted after confirming red.
        sinnix-audio-capture-suite = scriptRegistry.packageSet.sinnix-audio-capture;

        # Provably fails when: the debounce gate's suppress condition
        # inverts. Verified by flipping `< self._min_interval` to `>` in
        # debounce.py -- caught by three tests (two unit, one daemon
        # integration: 3 failed, 16 passed); reverted after confirming red.
        sinnix-capture-a11y-suite = scriptRegistry.packageSet.sinnix-capture-a11y;

        # Provably fails when: /today stops distinguishing open from closed
        # commitments. Verified by changing store.py's open_commitments query
        # from `status = 'open'` to `status = 'done'` -- caught by
        # test_today_renders_open_commitment_with_forecast (1 failed, 3
        # passed); reverted after confirming red. (Note: the sibling
        # /calibration "actual rate" assertion in test_app.py is vacuous --
        # its "100%" substring check also matches the page's unrelated
        # `table { width: 100%; }` CSS rule -- a pre-existing test-quality
        # defect, out of scope here since it isn't this task's reachability
        # question.)
        sinnix-cockpit-suite = scriptRegistry.packageSet.sinnix-cockpit;

        # Provably fails when: STRIP_SENTENCE rules stop dropping the
        # sentence they match (keep everything else). Verified by inverting
        # the `not pattern.search(s)` keep-predicate in filter.py -- caught
        # by four tests including the STRIP_SENTENCE case (4 failed, 4
        # passed); reverted after confirming red.
        sinnix-deslop-suite = scriptRegistry.packageSet.sinnix-deslop;

        # Provably fails when: send_token dedup stops recognizing a token
        # it's already seen. Verified by making seen_token() always return
        # False in execute.py -- caught by
        # test_second_execution_with_same_token_is_a_noop_duplicate (1
        # failed, 46 passed); reverted after confirming red.
        #
        # Built with a locally-configured nixpkgs instance: this package's
        # steerPackage dependency (sinnix-steer) carries pkgs.claude-code on
        # its runtimeInputs, and claude-code is unfree -- plain legacyPackages
        # (the unconfigured instance every other check here uses) refuses to
        # even evaluate its drvPath. Same pattern as
        # flake/overlay/package/local-ai.nix's aiPkgs, scoped to this one
        # check rather than flipping allowUnfree tree-wide.
        sinnix-phone-dispatcher-suite = scriptRegistryUnfree.packageSet.sinnix-phone-dispatcher;

        # Provably fails when: the project-path sandbox stops rejecting a
        # path that resolves outside the project root (e.g. via a symlink).
        # Verified by neutering `_safe_path`'s escape check (`root not in
        # resolved.parents` -> `False`) in projects.py -- caught by
        # test_project_tree_and_read_reject_symlink_escape ("DID NOT RAISE
        # ProjectError"; 1 failed, 23 passed); reverted after confirming red.
        sinnix-agent-gateway-suite = scriptRegistry.packageSet.sinnix-agent-gateway;

        # Owner-execution has daemon and adapter consumers. This package check
        # exercises its bounded subprocess contract at its package boundary.
        sinnix-mcp-suite = scriptRegistry.packageSet.sinnix-mcp;

        # Provably fails when: the launch input stops carrying the descriptor's
        # argv, pool, label or artifact paths, or the pueue adapter misreads
        # the daemon's JSON. The suite drives a private pueued end to end.
        sinnixd-suite = scriptRegistry.packageSet.sinnixd;
      };
    };
}
