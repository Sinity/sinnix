# Shared output contract for unit-owned and externally produced captures.
{ lib }:
lib.types.submodule {
  options = {
    name = lib.mkOption { type = lib.types.str; };
    path = lib.mkOption { type = lib.types.str; };
    producerProgressPath = lib.mkOption {
      type = lib.types.nullOr lib.types.str;
      default = null;
      description = ''
        Optional producer-owned marker updated only after real output is
        committed. The health sweep can stat this one path when its bounded
        file scan cannot determine freshness.
      '';
    };
    cadenceSeconds = lib.mkOption {
      type = lib.types.nullOr lib.types.int;
      default = null;
    };
    eventDriven = lib.mkOption {
      type = lib.types.bool;
      default = false;
    };
    staleAfterSeconds = lib.mkOption {
      type = lib.types.nullOr lib.types.int;
      default = null;
      description = ''
        Absolute staleness budget in seconds, independent of
        cadenceSeconds. Event-driven lanes (eventDriven = true)
        have no numeric cadence for the health sweep's 2*cadence
        staleness check, so this is the only signal that flags
        them stale when writes stop. Lanes with a numeric
        cadenceSeconds may set this too; the health sweep flags a
        lane stale when EITHER threshold is exceeded.
      '';
    };
    livenessProbe = lib.mkOption {
      type = lib.types.nullOr (
        lib.types.submodule {
          options = {
            command = lib.mkOption {
              type = lib.types.str;
              description = ''
                Shell snippet (run as `bash -c "$command"` under
                `timeout`) answering "is the thing this lane
                observes actually present and publishing?" --
                a check on the UPSTREAM source, distinct from
                whether the lane's own unit is active
                (systemctl is-active is already covered
                elsewhere and is precisely the check that
                missed sinnix-pev0's a11y incident: the unit,
                listeners, and bus were all healthy while the
                AT-SPI registry root had zero children
                published).

                Exit-code contract the health sweep relies on:
                0 = present, 1 = confirmed absent, anything
                else (including a timeout's 124) = unknown.
                A probe that cannot determine the answer must
                exit something other than 0 or 1 -- silently
                exiting 0 on failure is exactly the bug class
                this option exists to catch.
              '';
            };
            timeoutSeconds = lib.mkOption {
              type = lib.types.ints.positive;
              default = 5;
              description = ''
                Bound on the probe's runtime. The health sweep runs
                on a 1-minute cadence against every capture
                lane, so a hung probe must not hang the sweep;
                a timeout is reported as unknown, never healthy.
              '';
            };
          };
        }
      );
      default = null;
      description = ''
        Optional upstream-liveness probe. Most lanes have no
        cheap probe available -- leave this null and the lane
        behaves exactly as it did before this option existed.
        staleAfterSeconds alone can only detect "no writes
        recently"; it structurally cannot distinguish a
        legitimately quiet lane from one whose upstream
        publisher never registered in the first place, so
        lanes where that distinction is cheaply checkable
        should declare a probe here instead of relying solely
        on a longer budget.
      '';
    };
    requiredPayloadFields = lib.mkOption {
      type = lib.types.listOf lib.types.str;
      default = [ ];
      example = [
        "window_class"
        "geometry.width"
      ];
      description = ''
        Dotted paths into a sinnix-capture-v1 record's `payload`
        that this lane claims to populate. The hub server's health sweep
        samples the lane's most recent records and flags the lane
        `degenerate` when a declared field is null/empty in EVERY
        sampled record -- the "alive and writing at full cadence,
        but the data is unconditionally null" failure the
        staleness check cannot see (screen-frames shipped that way
        for its whole deployed life; see sinnix-3w9n).

        Declare only fields a healthy record always carries.
        Fields that are legitimately absent sometimes (an optional
        subtitle, a nullable parent id) must NOT be listed: the
        check is deliberately all-or-nothing so a partially
        populated field is never an alarm, which means a
        sometimes-null field simply makes the check unable to
        fire. Leave empty for lanes whose captures are not
        JSONL envelopes.
      '';
    };
  };
}
